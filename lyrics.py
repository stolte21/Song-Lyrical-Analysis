""" 

  Utility analyzes lyrics to determine the most used words across genres
  and on a per artist basis. It web scrapes Genius with a given list of artists
  from a supplied JSON file. Since the lyrical content itself isn't
  visible using the Genius API, the API is used solely to get search results
  for each song. Once a song result is retrieved from the API, BeautifulSoup
  is used to scrape the URL and parse the lyrics.

  Lyrical results are saved in JSON format.

"""

import os
import sys
import configparser
import string
import json
import re
import glob
import urllib.request
from collections import Counter
from urllib.error import URLError, HTTPError
from time import sleep
from bs4 import BeautifulSoup

# =====================================
# - Constants
# =====================================

SEARCH_RESULTS_DIR = 'Search Response JSON'

ANALYSIS_RESULTS_DIR = 'Analysis Results'
ARTIST_RESULTS_FILE = 'artist_results.json'
GENRE_RESULTS_FILE = 'genre_results.json'

CLIENT_ID = 'client_id'
CLIENT_SECRET = 'client_secret'
CLIENT_ACCESS_TOKEN = 'client_access_token'

GENIUS_BASE_API_URL = 'http://api.genius.com'

# In case the script has been ran before, attempt to load
# the previous results as this will prevent re-doing uneccessary work.
try:
    with open(os.path.join(ANALYSIS_RESULTS_DIR, ARTIST_RESULTS_FILE), 'r') as f:
        ARTIST_RESULTS = json.load(f)
except OSError as e:
    ARTIST_RESULTS = {}

GENRES = ['Black Metal', 'Death Metal', 'Metalcore', 'Stoner Metal', 'Thrash Metal']

GENRE_RESULTS = {}
for genre in GENRES:
    GENRE_RESULTS[genre] = {}


# =====================================
# - Functions
# =====================================


# --- Init --- #
# ------------ #

def read_artists_json():
    """Retrieves data about a list of artists defined
       from a JSON file.


    Returns:
        A JSON object containing information
        about a list of artists.
    """
    return read_json('artist_list.json')

def get_credentials():
    """Retrieves Genius API credentials from a properties file.

    Returns:
        A dict containing keys needed to send
        successful requests to the Genius API.
    """
    keys = {}
    config = configparser.ConfigParser()
    config.read('credentials.ini')

    for key, value in config['credentials'].items():
        keys[key] = value

    return keys


# --- Genius API --- #
# ------------------ #

def search(term, client_access_token):
    """Execute the Genius API search function.

    Arguments:
        term: The search term fed to the API.
        client_access_token: Genius token needed for API use.

    Returns:
        A JSON object containing the results of the API request.
    """
    SEARCH_URL = '/search?q='
    
    results = []
    full_url = GENIUS_BASE_API_URL + SEARCH_URL + urllib.parse.quote(term)

    # Retrieve as many pages as defined by the range - 10 results per page
    for page in range(1,6):
        response = send_request(full_url+'&page='+str(page), client_access_token, True)
        if response:
            results.append(response)

    return results

def artist_songs(id, client_access_token):
    """Execute the Genius API GET /artists/:id/songs method

    Arguments:
        id: The Genius artist ID
        client_access_token: Genius token needed for API use.

    Returns:
        A JSON object containing the results of the API request.
    """
    ARTIST_SONGS_URL = f'/artists/{id}/songs?per_page=50&page=1'
    FULL_URL = f'{GENIUS_BASE_API_URL}{ARTIST_SONGS_URL}'
    response = send_request(FULL_URL, client_access_token, True)

    if response:
        return response['response']['songs']
    else:
        return []

# --- Lyric Data Collection --- #
# ----------------------------- #

def collect_genius_song_data(artists, creds):
    """Saves the results from the Genius search API.

    Iterates over the list of artists and saves the results
    for each artist as a JSON file.

    Arguments:
        artists: JSON object containing a list of artists
        creds: API credentials
    """
    for artist in artists['artists']:
        # The directory tree will already exist for artists that have been mined before,
        # so we can just skip that artist when that is the case.
        if not os.path.isdir(os.path.join(SEARCH_RESULTS_DIR, artist['genre'], artist['artist'])):
            print(artist['artist'])
            #results = search(artist['artist'], creds[CLIENT_ACCESS_TOKEN])
            results = artist_songs(artist['id'], creds[CLIENT_ACCESS_TOKEN])
            results = [x for x in results if x['primary_artist']['id'] == artist['id']]
            
            save_json(results, artist['artist'], artist['genre'], artist['artist'])
            sleep(3)    # Sleep for some amount of time so the Genius API doesn't get hammered with requests

def parse_all_song_data(artists, creds):
    """Analyzes all the saved API data.

    Scans each artist's directory for JSON files
    containing Genius API results. Web scrapes each song URL
    within each result to get the raw lyrics for analysis.
    """
    for artist in artists['artists']:
        print(artist['artist'])
        # This directory will already exist for artists that have already had lyrical data
        # analyzed. We can skip that artist when that is the case.
        if artist['artist'] not in ARTIST_RESULTS:
            artist_lyric_count = Counter()
            artist_json_files = glob.glob(os.path.join(SEARCH_RESULTS_DIR, artist['genre'], artist['artist'], '*.json'))
            parse_artist_data(artist_json_files, creds, artist_lyric_count)
            ARTIST_RESULTS[artist['artist']] = artist_lyric_count

def parse_artist_data(files, creds, artist_lyric_count):
    """Reads a directory containing files of artist data."""
    for file in files:
        parse_lyrics(os.path.abspath(file), creds, artist_lyric_count)

def parse_lyrics(songs_file, creds, lyric_dict):
    """Analyzes a file containing song lyric URLs.

    Each file contains multiple URLs, each URL pertaining
    to a specific song. The lyrics are extracted from the
    raw HTML to determine the word frequency in each song.

    """
    with open(songs_file, 'r') as json_file:
        json_data = json.load(json_file)

    for song in json_data:
        html = send_request(song['url'], creds[CLIENT_ACCESS_TOKEN], False)
        [h.extract() for h in html('script')]
        lyrics = html.find('div', class_='lyrics').get_text().lower()
        lyrics = re.sub(r'\[.*?\]', '', lyrics)
        lyrics = re.sub(r'[^\x00-\x7f]',r'', lyrics)
        lyrics = lyrics.translate(str.maketrans('', '', string.punctuation))
        add_counts_to_dict(lyrics.split(), lyric_dict)

        sleep(2)    # Sleep for some amount of time so the Genius website doesn't get hammered with requests


# --- Utility Methods --- #
# ----------------------- #

def save_results(artists):
    """Save the artist results and compute/save the genre results.  
    """
    for artist in artists['artists']:
        artist_counts = ARTIST_RESULTS[artist['artist']]
        add_dict(GENRE_RESULTS[artist['genre']], artist_counts)

    save_lyric_count(ARTIST_RESULTS, ARTIST_RESULTS_FILE)
    save_lyric_count(GENRE_RESULTS, GENRE_RESULTS_FILE)

def add_dict(source, supplement):
    """Combine the counts of two dictionaries into one.

    Iterates over the keys in supplement and merges
    them into the source dictionary.

    Arguments:
        source: the main dictionary
        supplement: the dictionary to be merged into source
    """
    for key in supplement:
        if key in source:
            source[key] += supplement[key]
        else:
            source[key] = supplement[key]

def add_counts_to_dict(data_set, data_dict):
    """Add each word in a list to a dictionary of counts.

    Arguments:
        data_set: The list of words to analyze.
        data_dict: The source dictionary to maintain counts of words.
    """

    data_set = remove_common_words(data_set)
    for word in data_set:
        strip_word = re.sub(r'[^\w\s]','', word)
        data_dict[strip_word] += 1

def send_request(url, access_token, is_api_request, data=None):
    """Send a request to the provided URL and return the results.

    Arguments:
        url: The request URL.
        access_token: The Genius API access token.
        is_api_request: True if using Genius API, otherwise HTML parse the response
        data: Optional data sent along with the request

    Returns:
        The response from the request either in JSON format or string.
    """
    user_agent = 'curl/7.9.8 (i686-pc-linux-gnu) libcurl 7.9.8 (OpenSSL 0.9.6b) (ipv6 enabled)'
    headers = {'User-Agent': user_agent, 'Authorization': 'Bearer ' + access_token}

    if data:
        data = urllib.parse.urlencode(data).encode('ascii')

    request = urllib.request.Request(url, data, headers)
    result = None

    try:
        with urllib.request.urlopen(request) as response:
            if is_api_request:
                result = response.read()
            else:
                result = BeautifulSoup(response, 'html.parser')
    except HTTPError as e:
        print("Server couldn't fulfill the request: ", e.code)
    except URLError as e:
        print("Failed to reach a server: ", e.reason)

    if result:
        if is_api_request:
            return json.loads(result)
        else:
            return result
    else:
        return None

def remove_common_words(word_list):
    """Remove common Stop Words from a list.

    These are some of the most common words of lyrics, so
    it'd be best to ignore them and focus on words which
    may distinguish songs from each other.
    """
    stop_words =   ['a', 'about', 'above', 'across', 'after', 'afterwards', 'again', 'against', 'all', 'almost', 'alone', 'along',
                    'already', 'also', 'although', 'always', 'am', 'among', 'amongst', 'amoungst', 'amount', 'an', 'and', 'another',
                    'any', 'anyhow', 'anyone', 'anything', 'anyway', 'anywhere', 'are', 'around', 'as', 'at', 'back', 'be', 'became',
                    'because', 'become', 'becomes', 'becoming', 'been', 'before', 'beforehand', 'behind', 'being', 'below',
                    'beside', 'besides', 'between', 'beyond', 'bill', 'both', 'bottom', 'but', 'by', 'call', 'can', 'cannot', 'cant',
                    'co', 'computer', 'con', 'could', 'couldnt', 'cry', 'de', 'describe', 'detail', 'did', 'do', 'done', 'dont', 'down', 'due',
                    'during', 'each', 'eg', 'eight', 'either', 'eleven', 'else', 'elsewhere', 'empty', 'enough', 'etc', 'even', 'ever',
                    'every', 'everyone', 'everything', 'everywhere', 'except', 'few', 'fifteen', 'fifty', 'fill', 'find', 'fire', 'first',
                    'five', 'for', 'former', 'formerly', 'forty', 'found', 'four', 'from', 'front', 'full', 'further', 'get', 'give',
                    'go', 'had', 'has', 'hasnt', 'have', 'he', 'hence', 'her', 'here', 'hereafter', 'hereby', 'herein', 'hereupon', 'hers',
                    'herself', 'him', 'himself', 'his', 'how', 'however', 'hundred', 'i', 'ie', 'if', 'ill', 'in', 'inc', 'indeed',
                    'interest', 'into', 'im', 'is', 'it', 'its', 'itself', 'keep', 'last', 'latter', 'latterly', 'least', 'less', 'like', 'ltd', 'made',
                    'many', 'may', 'me', 'meanwhile', 'might', 'mill', 'mine', 'more', 'moreover', 'most', 'mostly', 'move', 'much',
                    'must', 'my', 'myself', 'name', 'namely', 'neither', 'never', 'nevertheless', 'next', 'nine', 'no', 'nobody', 'none',
                    'noone', 'nor', 'not', 'nothing', 'now', 'nowhere', 'of', 'off', 'often', 'on','once', 'one', 'only', 'onto', 'or',
                    'other', 'others', 'otherwise', 'our', 'ours', 'ourselves', 'out', 'over', 'own', 'part', 'per', 'perhaps', 'please',
                    'put', 'rather', 're', 's', 'same', 'see', 'seem', 'seemed', 'seeming', 'seems', 'serious', 'several', 'she', 'should',
                    'show', 'side', 'since', 'sincere', 'six', 'sixty', 'so', 'some', 'somehow', 'someone', 'something', 'sometime',
                    'sometimes', 'somewhere', 'still', 'such', 'system', 'take', 'ten', 'than', 'that', 'thats', 'the', 'their', 'them', 'themselves',
                    'then', 'thence', 'there', 'theres', 'thereafter', 'thereby', 'therefore', 'therein', 'thereupon', 'these', 'they',
                    'thick', 'thin', 'third', 'this', 'those', 'though', 'three', 'three', 'through', 'throughout', 'thru', 'thus', 'to',
                    'together', 'too', 'top', 'toward', 'towards', 'twelve', 'twenty', 'two', 'un', 'under', 'until', 'up', 'upon',
                    'us', 'very', 'via', 'was', 'we', 'well', 'were', 'what', 'whatever', 'when', 'whence', 'whenever', 'where',
                    'whereafter', 'whereas', 'whereby', 'wherein', 'whereupon', 'wherever', 'whether', 'which', 'while', 'whither', 'who',
                    'whoever', 'whole', 'whom', 'whose', 'why', 'will', 'with', 'within', 'without', 'would', 'yet', 'you', 'your', 'youre', 'youll'
                    'yours', 'yourself', 'yourselves', 'youve']

    return [w for w in word_list if w not in stop_words]

def read_json(file_name):
    """Open the given file as json and return the result."""
    result = None
    with open(file_name, 'r') as f:
        result = json.load(f)
    return result

# --- Save Data --- #
# ----------------- #

def save_json(json_data, artist_name, genre, file_name):
    """Store Genius API JSON data"""
    save(json_data, os.path.join(SEARCH_RESULTS_DIR, genre, artist_name), file_name+'.json', 'w')

def save_lyric_count(artist_counts, lyric_file):
    """Store compiled artist lyrical data"""
    save(artist_counts, ANALYSIS_RESULTS_DIR, lyric_file, 'w')

def save(data, dir_name, file_name, mode):
    """Serialize an object and write it to a file."""
    os.makedirs(dir_name, exist_ok=True)
    with open(os.path.join(dir_name, file_name), mode) as f:
        json.dump(data, f)

# =====================================
# - Main
# =====================================

def main():

    creds = get_credentials()
    artists = read_artists_json()

    ## Step 1 -
    ## Use Genius API to gather song data for a list of artists
    print('Collection')
    collect_genius_song_data(artists, creds)

    ## Step 2 -
    ## Scrape Genius website with URLs from the
    ## gathered data and save the frequency analysis results.
    print('Analysis')
    parse_all_song_data(artists, creds)

    ## Step 3 -
    ## Store results as JSON object in a text file.
    print('Storage')
    save_results(artists)

if __name__ == "__main__":
    main()
# Song-Lyrical-Analysis
Python script that uses the Genius API and web scraping to analyze word frequency in music

## Getting started
Update the credentials.ini with your Genius API client ID and modify the artist_list.json to your liking. I filled it with popular metal, rap, and pop artists as a start.

## Running the script
Once you have your Genius API credentials and the artists you'd like to get results for, run the python script from the root directory.

```
python lyrics.py
```

## Results
The results of the script will be stored in the root directory in "Analysis Results" and the responses from the Genius API will all be stored in "Search Response JSON" - this way, rerunning the script will not poll the Genius API again for artist we've already gathered data for.

## Example
Here's an example of how the data for a certain artist can be displayed with a simple ChartJS graph.
![Example](https://i.imgur.com/ar1WaK6.png)

A full working example with all my sample data can be found (here)

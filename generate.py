import sqlite3
import requests
from bs4 import BeautifulSoup

# ====================== METHOD DEFINITIONS ========================

# builds list of song artists given string which contains one or more names
def buildArtistsList(artistStr):
    # fix \xa0 non-breaking space character
    artistStr = artistStr.replace('\xa0', ' ')
    if 'Feat.' not in artistStr and '&' not in artistStr and ',' not in artistStr:
        return [artistStr]
    artists = []
    # split string by "Feat."
    featSplit = artistStr.split(' Feat. ')
    for artistSet in featSplit:
        # build artists list by splitting by "&"
        artists.extend(artistSet.split(' & '))
    # split further by commas
    for artist in artists:
        if ',' in artist:
            addition = artist.split(', ')
            # remove combined artist then re-add addition list
            artists.remove(artist)
            artists.extend(addition)
    return artists

# returns True if songArtists contains at least one artist in desiredArtists
def songQualifies(songArtists):
    for artist in songArtists:
        if(binary_search(desiredArtists, artist)) > -1:
            return True
    return False

# implementation of binary search algorithm
# http://code.activestate.com/recipes/81188-binary-search/
def binary_search(seq, t):
    min = 0
    max = len(seq) - 1
    while True:
        if max < min:
            return -1
        m = (min + max) // 2
        if seq[m] < t:
            min = m + 1
        elif seq[m] > t:
            max = m - 1
        else:
            return m



# ====================== BEGIN SCRIPT ========================

# define desired artists list
desiredArtists = ['Future', '21 Savage', 'Travis Scott', 'Drake', 'Lil Baby', 'Lil Uzi Vert', 'Rae Sremmurd', 'Big Sean', 'Dave East', 
    'Cardi B', 'Offset', 'Young Thug', 'Swae Lee', 'The Weeknd', 'Desiigner', 'Joyner Lucas', 'Post Malone', 'Vory', 'Lil Pump', 
    'Kevin Gates', 'Jay Critch', 'Rich The Kid', 'Quavo', 'Migos', 'Tory Lanez', 'Meek Mill', 'A$AP Rocky']
# sort list (for binary search later)
desiredArtists.sort()

# connect to SQLite database for this script
conn = sqlite3.connect('script.db')
c = conn.cursor()

# song candidates are songs to be added to playlist if
# 1) they are on Spotify and
# 2) they haven't already been added to current/prev playlist
songCandidates = []

# get HTML of HotNewHipHop's "top 100" page
try:
    hnhhRequest = requests.get('https://www.hotnewhiphop.com/top100/')
    topSongsHtml = hnhhRequest.text
except:
    print('error getting top 100 list html')

# parse with BeautifulSoup
soup = BeautifulSoup(topSongsHtml, 'html.parser')

# build song candidates list
for songHtml in soup.find_all('div', class_='chartItem-body-artist'):
    songName = songHtml.a.text.strip()
    # remove (prod. by ...) from song name
    if '(' in songName: 
        songName = songName[:songName.index('(') - 1]

    songArtists = buildArtistsList(songHtml.div.text)
    # add to songCandidates if features at least one desired artist
    if songQualifies(songArtists):
        songCandidates.append((songName, songArtists))
print(songCandidates)

# close cursor and SQLite db connection
c.close()
conn.close()
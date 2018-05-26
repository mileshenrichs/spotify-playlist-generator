import sqlite3
import requests
from bs4 import BeautifulSoup
import urllib.parse

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

# obtain new Spotify access token using refresh_token
def getNewAccessToken():
    c.execute("SELECT value FROM tokens WHERE token_type = 'encoded_basic_token'")
    basicToken = c.fetchone()[0]
    c.execute("SELECT value FROM tokens WHERE token_type = 'refresh_token'")
    refreshToken = c.fetchone()[0]

    reqHeader = {'Authorization': 'Basic {}'.format(basicToken)}
    reqBody = {'grant_type': 'refresh_token', 'refresh_token': refreshToken}
    r = requests.post('https://accounts.spotify.com/api/token', headers=reqHeader, data=reqBody)
    print('status: ' + str(r.status_code))
    resJson = r.json()
    
    newToken = resJson['access_token']
    # update token in db
    c.execute("UPDATE tokens SET value = ? WHERE token_type = 'access_token'", (newToken,))
    conn.commit()

    return newToken

# return track id from Spotify search endpoint given song title and artists
def findSong(name, artists):
    songId = ''

    reqHeader = {'Authorization': 'Bearer {}'.format(spotifyToken)}
    queryParams = '?q={}&type=track&market=US&limit=5'.format(urllib.parse.quote(name))
    r = requests.get('https://api.spotify.com/v1/search' + queryParams, headers=reqHeader)
    res = r.json()

    # iterate through results
    for result in res['tracks']['items']:
        trackArtists = result['artists']
        trackArtistsNames = list(map((lambda artist: artist['name']), trackArtists))
        # take intersection of trackArtists and desiredArtists lists
        artistsInCommon = [artist for artist in trackArtistsNames if artist in desiredArtists]

        # if at least one artist matches and names are approx. equal, set songId
        if artistsInCommon and name.lower() in result['name'].lower():
            songId = result['id']
            break

    return songId


# ====================== BEGIN SCRIPT ========================

# define desired artists list
desiredArtists = ['Future', '21 Savage', 'Travis Scott', 'Drake', 'Lil Baby', 'Lil Uzi Vert', 'Rae Sremmurd', 'Big Sean', 'Dave East', 
    'Cardi B', 'Offset', 'Young Thug', 'Swae Lee', 'The Weeknd', 'Desiigner', 'Joyner Lucas', 'Post Malone', 'Vory', 'Lil Pump', 
    'Kevin Gates', 'Jay Critch', 'Rich The Kid', 'Quavo', 'Migos', 'Tory Lanez', 'Meek Mill', 'A$AP Rocky', 'Jazz Cartier', 'Kodak Black']
# sort list (for binary search later)
desiredArtists.sort()

# connect to SQLite database for this script
conn = sqlite3.connect('script.db')
c = conn.cursor()

# fetch Spotify access token (for my account)
c.execute("SELECT value FROM tokens WHERE token_type = 'access_token'")
spotifyToken = c.fetchone()[0]
# first, test current access token
reqHeader = {'Authorization': 'Bearer {}'.format(spotifyToken)}
testRequest = requests.get('https://api.spotify.com/v1/me', headers=reqHeader)
# if unauthorized, need to refresh access token
if testRequest.status_code in [401, 403]:
    spotifyToken = getNewAccessToken()

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

# define song ids to add list
songIdsToAdd = []

for candidate in songCandidates:
    # make sure song hasn't already been added to previous playlist
    isDuplicate = False
    c.execute("SELECT * FROM songs_added WHERE song_name = ?", (candidate[0],))
    for row in c.fetchall():
        if row[0] == candidate[0] and row[1] == candidate[1][0]:
            isDuplicate = True
    if isDuplicate: # skip over this song if it's a duplicate
        continue

    # find song id on Spotify via search endpoint
    songId = findSong(candidate[0], candidate[1])
    if songId:
        songIdsToAdd.append(songId)

print(songIdsToAdd)

# close cursor and SQLite db connection
c.close()
conn.close()
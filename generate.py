import sqlite3
import requests
from bs4 import BeautifulSoup
import urllib.parse
import datetime

# ====================== METHOD DEFINITIONS ========================

def authHeader():
    return {'Authorization': 'Bearer {}'.format(spotifyToken)}

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
    resJson = r.json()
    
    newToken = resJson['access_token']
    # update token in db
    c.execute("UPDATE tokens SET value = ? WHERE token_type = 'access_token'", (newToken,))
    conn.commit()

    return newToken

# return track id from Spotify search endpoint given song title and artists
def findSong(name, artists):
    songId = ''

    queryParams = '?q={}&type=track&market=US&limit=5'.format(urllib.parse.quote(name))
    r = requests.get('https://api.spotify.com/v1/search' + queryParams, headers=authHeader())
    res = r.json()

    # iterate through results
    for result in res['tracks']['items']:
        trackArtists = result['artists']
        trackArtistsNames = list(map((lambda artist: artist['name']), trackArtists))
        # take intersection of trackArtists and desiredArtists lists
        artistsInCommon = [artist for artist in trackArtistsNames if artist in artists]

        # if at least one artist matches and names are approx. equal, set songId
        if artistsInCommon and name.lower() in result['name'].lower():
            songId = result['id']
            break

    return songId

# returns today's date as simple string (i.e. 10/08, 4/22)
def getTodaysDate():
    todaysDate = datetime.datetime.today().strftime('%m/%d')
    if todaysDate[0] == '0':
        todaysDate = todaysDate[1:]
    return todaysDate

# converts special characters to their basic form (for string comparison)
def normalizeNames(names):
    # check type (if single element, return as single element)
    if type(names) == str:
        name = names.lower().replace('ë', 'e').replace('í', 'i').replace('ñ', 'n')
        return name
    # make replacements
    for i in range(len(names)):
        names[i] = names[i].lower().replace('ë', 'e').replace('í', 'i').replace('ñ', 'n')
    return names    

# removes any trailing details from song name (i.e. "(prod. by ...)" or "feat ...")
def getTrueSongName(songName):
    trueSongName = songName[:songName.index(' (')] if '(' in songName else songName
    trueSongName = trueSongName[:trueSongName.index(' feat')] if 'feat' in trueSongName else trueSongName
    return trueSongName

# builds a new playlist on my Spotify account w/ tracks corresponding to provided song ids
def createPlaylist(songIds):
    # initialize playlist
    todaysDate = getTodaysDate()
    c.execute("SELECT value FROM tokens WHERE token_type = 'spotify_id'")
    spotifyUserId = c.fetchone()[0]
    playlistName = 'New Songs {}'.format(todaysDate)

    reqHeader = {'Authorization': 'Bearer {}'.format(spotifyToken), 'Content-Type': 'application/json'}
    reqBody = {'name': playlistName, 'description': 'This playlist was built by a script.  See how it works at: https://github.com/mileshenrichs/spotify-playlist-generator'}
    r = requests.post('https://api.spotify.com/v1/users/{}/playlists'.format(spotifyUserId), headers=reqHeader, json=reqBody)
    
    if r.status_code in [200, 201]:
        newPlaylistId = r.json()['id']
        # create record in db for new playlist
        c.execute("INSERT INTO playlists_created (spotify_playlist_id, playlist_name) VALUES (?, ?)", (newPlaylistId, playlistName))
        conn.commit()
    
    # add tracks to playlist
    addTracksToPlaylist(newPlaylistId, playlistName, songIds)

# place tracks with given ids into Spotify playlist with given id and name
def addTracksToPlaylist(playlistId, playlistName, songIds):
    # get user id (used in request)
    c.execute("SELECT value FROM tokens WHERE token_type = 'spotify_id'")
    userId = c.fetchone()[0]

    # first, add tracks to songs_added playlist (to prevent future duplicates)
    for songId in songIds:
        # get song details
        r = requests.get('https://api.spotify.com/v1/tracks/{}'.format(songId), headers=authHeader())
        res = r.json()
        songName = res['name']
        songPrimaryArtist = res['artists'][0]['name']
        
        # create entry in db
        c.execute("INSERT INTO songs_added VALUES (?, ?, ?, datetime('now', 'localtime'))", (songName, songPrimaryArtist, playlistName))
    conn.commit()

    # send request to add tracks to Spotify playlist
    reqHeader = {'Authorization': 'Bearer {}'.format(spotifyToken), 'Content-Type': 'application/json'}
    reqBody = {'uris': list(map((lambda songId: 'spotify:track:' + songId), songIds))}

    r = requests.post('https://api.spotify.com/v1/users/{}/playlists/{}/tracks'.format(userId, playlistId), 
            headers=reqHeader, json=reqBody)


# ====================== BEGIN SCRIPT ========================

# define desired artists list
desiredArtists = ['Future', '21 Savage', 'Travis Scott', 'Drake', 'Lil Baby', 'Lil Uzi Vert', 'Rae Sremmurd', 'Big Sean', 'Dave East', 
    'Cardi B', 'Offset', 'Young Thug', 'Swae Lee', 'The Weeknd', 'Desiigner', 'Joyner Lucas', 'Post Malone', 'Vory', 'Lil Pump', 
    'Kevin Gates', 'Jay Critch', 'Rich The Kid', 'Quavo', 'Migos', 'Tory Lanez', 'Meek Mill', 'A$AP Rocky', 'Jazz Cartier', 
    'Kodak Black', '6LACK', 'Madeintyo']
# sort list (for binary search later)
desiredArtists.sort()

# connect to SQLite database for this script
conn = sqlite3.connect('script.db')
c = conn.cursor()

# fetch Spotify access token (for my account)
c.execute("SELECT value FROM tokens WHERE token_type = 'access_token'")
spotifyToken = c.fetchone()[0]
# first, test current access token
testRequest = requests.get('https://api.spotify.com/v1/me', headers=authHeader())
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
    c.execute("SELECT * FROM songs_added WHERE song_name LIKE ?", (candidate[0] + '%',))
    for row in c.fetchall():
        trueSongName = getTrueSongName(row[0])
        if normalizeNames(trueSongName) == normalizeNames(candidate[0]) and normalizeNames(row[1]) in normalizeNames(candidate[1]):
            isDuplicate = True
    if isDuplicate: # skip over this song if it's a duplicate
        continue

    # find song id on Spotify via search endpoint
    songId = findSong(candidate[0], candidate[1])
    if songId:
        songIdsToAdd.append(songId)

# determine day of week
dayOfWeek = int(datetime.datetime.today().strftime('%u'))
# new playlist if it's Saturday, else add to most recent playlist
if dayOfWeek == 6:
    createPlaylist(list(set(songIdsToAdd))) # make sure all songs are unique
else:
    c.execute("SELECT spotify_playlist_id, playlist_name FROM playlists_created WHERE id = (SELECT MAX(id) FROM playlists_created)")
    currentPlaylist = c.fetchone()
    addTracksToPlaylist(currentPlaylist[0], currentPlaylist[1], songIdsToAdd)

# close cursor and SQLite db connection
c.close()
conn.close()
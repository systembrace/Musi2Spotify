from flask import *
import os
from threading import Thread
import requests
from requests_html import HTMLSession
import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
import re
from match_strings import *
from sql_interface import *

app=Flask(__name__)

with open("secrets.env","r") as f:
    secrets=json.loads(f.read())

app.secret_key=secrets["SECRET_KEY"]

oauth=SpotifyOAuth(
    client_id=secrets["APP_CLIENT_ID"],
    client_secret=secrets["APP_CLIENT_SECRET"],
    redirect_uri=secrets["APP_REDIRECT_URI"],
    scope="playlist-modify-public"
)

htmlsession=HTMLSession()
htmlsession.browser

def spotify_client(token):
    try:
        return spotipy.Spotify(auth=token, auth_manager=SpotifyClientCredentials(secrets["APP_CLIENT_ID"], secrets["APP_CLIENT_SECRET"]), requests_timeout=10, retries=5)
    except Exception as e:
        print("EXCEPTION:"+e)
        return None

def refresh_token():
    session["token_info"]=oauth.refresh_access_token(session["refresh_token"])
    print(session["user_token"])
    session["user_token"] = session["token_info"]["access_token"]
    session["refresh_token"] = session["token_info"]["refresh_token"]

def scrape_playlist(link):
    global htmlsession
    songs=[]
    playlist_name=""
    total_songs=0
    scraped_songs=0
    load_error="Webscraping failed. Please try again"

    r=htmlsession.get(link)
    try:
        r.html.render(sleep=1)
    except Exception as e:
        load_error="Failed to connect to HTMLSession"
        print(e)
        requests.post("https://www.systembrace.com/refresh_htmlsession")
        currently_loading=False
        return songs, playlist_name, total_songs, scraped_songs, currently_loading, load_error
    r=r.html.html
    playlist_name=r[r.find('playlist_header_title">')+23:]
    playlist_name=playlist_name[:playlist_name.find("</div>")]
    r=r[r.find("video_title")+1:]
    r=r[r.find('href="')+1:]
    r=r[r.find('href="')+1:]
    total_songs=r.count('href="')
    while r.find('href="')!=-1:
        r=r[r.find('href="')+6:]
        url=r[:r.find('"')]
        thumb=r[r.find("url('")+5:]
        thumb=thumb[:thumb.find("'")]
        title=r[r.find("video_title")+13:]
        title=title[:title.find("</div>")]
        artist=r[r.find("video_artist")+14:]
        artist=artist[:artist.find("</div>")]
        if title[0]!=">":
            songs.append({"artist":artist,"title":title,"url":url,"thumb":thumb})
            scraped_songs+=1
            #print(artist)
            #print(title)
    return songs, playlist_name, total_songs, scraped_songs, True, ""

def artist_search(artist_name, spotify):
    artist_name=clean_artist(artist_name)
    artists_found=spotify.search(q=artist_name, type='artist',limit=5)['artists']['items']
    for artist in artists_found:
        if match(artist_name,clean_artist(artist['name']),max_misses=0):
            return artist
    return None

def artist_search_in_title(song_name, spotify):
    song_name=clean_song(song_name)
    search=spotify.search(q=song_name, type='artist,track',limit=5)
    artists_found=search['artists']['items']
    songs_found=search['tracks']['items']
    for artist in artists_found:
        if match(song_name,clean_artist(artist['name']),max_misses=0):
            return artist
    for song in songs_found:
        for artist in song['artists']:
            if match(song_name,artist['name'],max_misses=0):
                return artist
    return None

def song_search_artist(_song_name,artist_name,spotify):
    artist_name=clean_artist(artist_name)
    song_name=clean_song(_song_name).replace(artist_name,"").strip()
    songs_found=spotify.search(q=f"{song_name} - {artist_name}", type='track',limit=5)['tracks']['items']
    for song in songs_found:
        for artist in song['artists']:
            if match(song_name,song['name']) and match(artist_name,artist['name']):
                return song
    return None

def song_search(song_name,spotify):
    song_name=clean_song(song_name)
    songs_found=spotify.search(q=song_name, type='track',limit=5)['tracks']['items']
    for song in songs_found:
        for artist in song['artists']:
            if match(song_name,song['name'],1) or (match(song_name,song['name']) and match(song_name,artist['name'],max_misses=0)) or (match(song_name,song['name'],max_misses=0) and match(song_name,artist['name'],max_misses=0)):
                return song
    return None

def add_match(matches,musi,sp,index=0,remove=False,user_token=""):
    if not "album" in sp.keys():
        spotify=spotify_client(user_token)
        sp=spotify.track("open.spotify.com/track/"+sp["id"])
    res={
        "yt_title":truncate(musi["title"],27),
        "yt_author":truncate(musi["artist"]),
        "yt_url":musi["url"],
        "yt_thumb":musi["thumb"],
        "sp_title":truncate(sp["name"],27),
        "sp_artist":truncate(sp["artists"][0]["name"]),
        "sp_id":sp["id"],
        "sp_thumb":sp["album"]["images"][0]["url"]
    }
    for match in matches:
        if match["yt_url"]==musi["url"]:
            matches.remove(match)
            break
    if not remove:
        matches.insert(index,res)
    return sp


def refresh_thread_data(connection, user_token):
    data=get_playlist_data(connection, user_token)
    return (data[1], bool(data[3]), data[4], json.loads(data[5]), json.loads(data[6]), json.loads(data[7]), json.loads(data[8]), data[9], data[10], data[11])

def convert_playlist(link, user_token, refresh_token):
    load_error="Unknown Error"
    currently_loading=True
    playlist_name=""
    youtube_songs=[]
    spotify_songs=[]
    matches=[]
    not_found=[]
    total_songs=0
    scraped_songs=0
    matched_songs=0

    attempts=0

    db_connection=connect_to_db()

    link=link.replace(" ","")
    if not link.startswith("https://feelthemusi.com/playlist/") and not link.startswith("feelthemusi.com/playlist/"):
        load_error="Not a valid musi playlist. Copy the link found in the musi app.\nExample: https://feelthemusi.com/playlist/ABCDEF"
        currently_loading=False
        update_playlist_conversion(db_connection, user_token, load_error, currently_loading)
        return
    while len(youtube_songs)==0 and attempts<20:
        attempts+=1
        youtube_songs,playlist_name,total_songs,scraped_songs,currently_loading,load_error=scrape_playlist(link)
        #print(currently_loading)
        #if not currently_loading:
        #    update_playlist_conversion(db_connection, user_token, load_error, currently_loading)
        #    print("exited thread early")
        #    return
    if attempts>=20 and len(youtube_songs)==0:
        #load_error="Webscraping failed. Please try again"
        currently_loading=False
        update_playlist_conversion(db_connection, user_token, load_error, currently_loading)
        return

    print("Playlist scraped successfully. Starting search.\n")

    artistmatch={}
    spotify=spotify_client(user_token)
    if spotify is None:
        load_error="Your access token has expired. Please retry."
        currently_loading=False
        update_playlist_conversion(db_connection, user_token, load_error, currently_loading)
        return
    for musi_song in reversed(youtube_songs):
        currently_loading=playlist_is_loading(db_connection, user_token)
        if not currently_loading:
            load_error="Unknown error"
            print("exited thread early")
            update_playlist_conversion(db_connection, user_token, load_error, currently_loading)
            return
        update_playlist_conversion(db_connection, user_token, load_error, currently_loading, playlist_name, youtube_songs, spotify_songs, matches, not_found, total_songs, scraped_songs, matched_songs)
        match=match_song_registry(db_connection,musi_song)
        if match is not None and len(match)==1:
            if match[0][2]!="":
                song=json.loads(match[0][3])
                if not "album" in song.keys():
                    song=spotify.track("open.spotify.com/track/"+song["id"])
                matched_songs+=1
                add_match(matches, musi_song,song, 0, False, user_token)
                spotify_songs.append(song)
            else:
                matched_songs+=1
                res={
                    'title': truncate(musi_song['title'],27),
                    'url': musi_song['url'],
                    'artist': truncate(musi_song['artist']),
                    'thumb': musi_song['thumb']
                }
                not_found.insert(0,res)
                spotify_songs.append({})
            continue
        elif match is None:
            load_error="Disconnected from link registry database. Please try again later."
            currently_loading=False
            update_playlist_conversion(db_connection, user_token, load_error, currently_loading)
            return
        artist=None
        if musi_song['artist'] not in artistmatch:
            for poss_artist in artistmatch.keys():
                if artistmatch[poss_artist] is not None and artistmatch[poss_artist]['name'].lower() in musi_song['title'].lower():
                    artist=artistmatch[poss_artist]
                    #print("previously found artist "+artist['name']+" in title")
                    break
            if artist is None:
                artist=artist_search(musi_song['artist'],spotify)
                if artist is not None:
                    artistmatch[musi_song['artist']]=artist
                    #print("artist "+artist['name'])
                else:
                    artist=artist_search_in_title(musi_song['title'],spotify)
                    if artist is not None:
                        pass
                        #print("artist "+artist['name']+" in title")
                    else:
                        artistmatch[musi_song['artist']]=artist
        else:
            artist=artistmatch[musi_song['artist']]
            #if artist is not None:
                #print("previously found artist "+artist['name'])

        if artist is not None:
            song=song_search_artist(musi_song['title'],artist['name'],spotify)
            if song is not None:
                spotify_songs.append(song)
                matched_songs+=1
                song=add_match(matches,musi_song,song, 0, False, user_token)
                add_song_to_registry(db_connection,musi_song,song)
                #print("found "+song['name']+" by "+song['artists'][0]['name'])
                continue
            #else:
            #    session["not_found"].append(musi_song)
            #    print(musi_song['title']+" not found")
            #continue

        song=song_search(musi_song['title'],spotify)
        if song is not None:
            spotify_songs.append(song)
            matched_songs+=1
            song=add_match(matches,musi_song,song, 0, False, user_token)
            add_song_to_registry(db_connection,musi_song,song)
            #print("found "+song['name']+" by "+song['artists'][0]['name']+" without artist")
        else:
            res={
                'title': truncate(musi_song['title'],27),
                'url': musi_song['url'],
                'artist': truncate(musi_song['artist']),
                'thumb': musi_song['thumb']
            }
            not_found.insert(0,res)
            spotify_songs.append({})
            matched_songs+=1
            add_song_to_registry(db_connection,musi_song,{})
            #print(musi_song['title']+" not found")

    print("\nDone. printing results:\n")

    #for song in session["spotify_songs"]:
    #    print("found "+song['name']+" by "+song['artists'][0]['name'])
    #print()
    #for song in session["not_found"]:
    #    print("didn't find "+song['title'])
    #print()
    print(str(len(spotify_songs))+" songs found of "+str(len(youtube_songs))+" total")

    currently_loading=False
    update_playlist_conversion(db_connection, user_token, load_error, currently_loading, playlist_name, youtube_songs, spotify_songs, matches, not_found, total_songs, scraped_songs, matched_songs)
    db_connection.disconnect()

@app.route('/', methods=["GET","POST"])
def homepage():
    print("loaded homepage")
    if "code" in request.args:
        session["token_info"] = oauth.get_access_token(request.args["code"])
        session["user_token"] = session["token_info"]["access_token"]
        session["refresh_token"] = session["token_info"]["refresh_token"]
    if "user_token" in session and session["user_token"]!="" and "refresh_token" in session and session["refresh_token"]!="" and oauth.validate_token(session["token_info"]) and spotify_client(session["user_token"])!=None:
        try:
            refresh_token()
        except:
            if ".cache" in os.listdir():
                os.remove(".cache")
            return render_template("login_page.html")
        print("logged in")
        db_connection=connect_to_db()
        delete_playlist_data(db_connection,session["user_token"])
        db_connection.disconnect()
        return render_template("index.html")
    else:
        if ".cache" in os.listdir():
            os.remove(".cache")
        return render_template("login_page.html")

@app.route("/login", methods=["GET","POST"])
def login():
    auth_url = oauth.get_authorize_url()
    return redirect(auth_url)

@app.route("/error", methods=["GET","POST"])
def error():
    db_connection=connect_to_db()
    load_error = refresh_thread_data(db_connection(), session["user_token"])[0]
    db_connection.disconnect()
    return render_template("error.html", ERROR=load_error)

@app.route('/link', methods = ["GET","POST"])
def link():
    if request.method == 'POST':
        refresh_token()
        #print(session["user_token"])
        db_connection=connect_to_db()
        update_playlist_conversion(db_connection,session["user_token"],"Unknown error",True)
        db_connection.disconnect()
        t=Thread(target=convert_playlist,args=(request.form["link"],session["user_token"],session["refresh_token"]))
        t.start()
        return redirect("/load_playlist", code=307)
    return redirect("/")

@app.route('/load_playlist', methods = ["GET","POST"])
def load_playlist():
    if request.method == "POST":
        return render_template("playlist.html")
    return redirect("/")

@app.route("/refresh_htmlsession", methods = ["GET","POST"])
def refresh_htmlsession():
    global htmlsession
    if request.method == "POST":
        htmlsession=HTMLSession()
        htmlsession.browser
        print("refreshed htmlsession")
    return redirect("/")

@app.route("/get_live_info",methods=["GET","POST"])
def get_live_info():
    db_connection=connect_to_db()
    load_error, currently_loading, playlist_name, youtube_songs, spotify_songs, matches, not_found, total_songs, scraped_songs, matched_songs = refresh_thread_data(db_connection, session["user_token"])
    db_connection.disconnect()
    if request.method == 'GET':
        return {"name":playlist_name,"songs":total_songs,"matched":matched_songs,"scraped":scraped_songs,"loading":currently_loading,"matches":matches,"not_found":not_found}
    return redirect("/")

@app.route("/get_song",methods=["GET","POST"])
def get_song():
    if request.method=="POST":
        body=json.loads(request.data)
        url=body["url"]
        res={"yt_title":"Not found"}
        db_connection=connect_to_db()
        youtube_songs=refresh_thread_data(db_connection, session["user_token"])[3]
        db_connection.disconnect()
        for song in youtube_songs:
            if song["url"]==url:
                res["yt_title"]=song["title"]
                break
        return res
    return redirect("/")

@app.route("/update_match",methods=["GET","POST"])
def update_match():
    if request.method=="POST":
        spotify=spotify_client(session["user_token"])
        if spotify is None:
            refresh_token()
            spotify=spotify_client(session["user_token"])
        body=json.loads(request.data)
        yt_url=body["yt_url"]
        sp_url=body["sp_url"]
        remove=body["remove"]
        db_connection=connect_to_db()
        load_error, currently_loading, playlist_name, youtube_songs, spotify_songs, matches, not_found, total_songs, scraped_songs, matched_songs = refresh_thread_data(db_connection, session["user_token"])
        if not remove:
            for match in matches:
                if match["yt_url"]==yt_url:
                    if match["sp_id"]==sp_url.replace("open.spotify.com/track/","").replace("https://","").replace("http://",""):
                        return {"message":"Link specified is already matched to the same song"}
                    break
        yt_song={}
        sp_song={}
        index=-1
        for i in range(0,len(youtube_songs)):
            song=youtube_songs[i]
            if song["url"]==yt_url:
                yt_song=song
                index=i
                break
        if index==-1:
            db_connection.disconnect()
            return {"message":"Video not found in original playlist. Try again."}
        try:
            sp_song=spotify.track(sp_url)
        except:
            db_connection.disconnect()
            return {"message":"Error searching for Spotify track.\nAre you sure this link is valid?"}
        try:
            if not remove:
                add_song_to_registry(db_connection,yt_song,sp_song,1)
            else:
                add_song_to_registry(db_connection,yt_song,{},1)
        except:
            db_connection.disconnect()
            return {"message":"Error adding match to registry. Please try again."}
        nf_song={
            'title': truncate(yt_song['title'],27),
            'url': yt_song['url'],
            'artist': truncate(yt_song['artist']),
            'thumb': yt_song['thumb']
        }
        if not remove:
            in_not_found=False
            for nf in not_found:
                if nf["url"]==nf_song["url"]:
                    not_found.remove(nf)
                    in_not_found=True
                    break
            if not in_not_found:
                spotify_songs.pop(len(spotify_songs)-index-1)
            spotify_songs.insert(len(spotify_songs)-index,sp_song)
            add_match(matches, yt_song,sp_song,index-len(not_found), False, session["user_token"])
        else:
            not_found.insert(0,nf_song)
            for song in spotify_songs:
                if song!={} and song["id"]==sp_url.replace("open.spotify.com/track/","").replace("https://","").replace("http://",""):
                    spotify_songs.remove(song)
                    spotify_songs.insert(len(spotify_songs)-index,{})
                    break
            add_match(matches, yt_song,sp_song,index,True, session["user_token"])
        update_playlist_conversion(db_connection, session["user_token"], load_error, currently_loading, playlist_name, youtube_songs, spotify_songs, matches, not_found, total_songs, scraped_songs, matched_songs)
        db_connection.disconnect()
        return {"message":"Success"}
    return redirect("/")

@app.route("/create_playlist",methods=["POST","GET"])
def create_playlist():
    if request.method=="POST":
        spotify=spotify_client(session["user_token"])
        if spotify is None:
            refresh_token()
            spotify=spotify_client(session["user_token"])
        existing_id=json.loads(request.data)["url"].replace("open.spotify.com/playlist/","").replace("https://","").replace("http://","")
        tracks=[]
        count=0
        db_connection=connect_to_db()
        load_error, currently_loading, playlist_name, youtube_songs, spotify_songs, matches, not_found, total_songs, scraped_songs, matched_songs = refresh_thread_data(db_connection, session["user_token"])
        db_connection.disconnect()
        for song in reversed(spotify_songs):
            if song!={}:
                if count%99==0:
                    tracks.append([])
                tracks[int(count/100)].append(song["uri"])
                count+=1
        playlist={}
        if existing_id=="":
            playlist=spotify.user_playlist_create(spotify.current_user()["id"],playlist_name)
        else:
            try:
                playlist=spotify.playlist(existing_id)
                spotify.playlist_replace_items(playlist["id"],[])
            except:
                return {"message":"Error: playlist not found."}
        for batch in tracks:
            spotify.playlist_add_items(playlist["id"],batch)
        print("Converted playlist successfully")
        return {"message":"Success","link":"https://open.spotify.com/playlist/"+playlist["id"]}
    return redirect("/")

if __name__=="__main__":
    app.run(debug=True, host="0.0.0.0")
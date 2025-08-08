import mysql.connector
from mysql.connector import Error
import json
from time import time

def connect_to_db():
    with open("secrets.env","r") as f:
        secrets=json.loads(f.read())
    connection=None
    try:
        connection = mysql.connector.connect(
            host="systembrace.mysql.pythonanywhere-services.com",
            user="systembrace",
            password=secrets["SQL_PW"],
            database="systembrace$link_registry"
        )
    except Error as e:
        print(f"{e}")
    return connection

def execute(connection, query):
    try:
        connection.cursor().execute(query)
        connection.commit()
    except Error as err:
        print(f"Execute error: '{err}'")

def read(connection, query):
    res=None
    cursor=connection.cursor()
    try:
        cursor.execute(query)
        res=cursor.fetchall()
    except Error as err:
        print(f"Read error: '{err}'")
    return res

def match_song_registry(connection, musi):
    query=f'SELECT * FROM link_registry WHERE url="{musi["url"]}"'
    res=None
    if connection is not None:
        res=read(connection,query)
    return res

def prep_string(string):
    return string.replace("'","''").replace('"','\\\"')

def prep_sp_song(sp):
    if sp=={}:
        return sp
    res={
        "name":prep_string(sp["name"]),
        "uri":sp["uri"],
        "id":sp["id"],
        "album":{"images":[{"url":sp["album"]["images"][0]["url"]}]},
        "artists":[{"name":prep_string(sp["artists"][0]["name"])}]
    }
    return res

def prep_song(song):
    res={}
    for key in song.keys():
        res[key]=prep_string(song[key])
    return res

def add_song_to_registry(connection, musi,sp,verified=0):
    query=f"REPLACE INTO link_registry VALUES ('{musi["url"]}',{verified},'{""}','{{}}');"
    if sp!={}:
        res=prep_sp_song(sp)
        query=f"REPLACE INTO link_registry VALUES ('{musi["url"]}',{verified},'{res["uri"]}','{json.dumps(res)}');"
    if connection is not None:
        execute(connection,query)
    else:
        print(f"Failed to add song {sp["name"]}")

def update_playlist_conversion(connection, token, load_error, currently_loading, playlist_name="", youtube_songs=[], spotify_songs=[], matches=[], not_found=[], total_songs=0, scraped_songs=0, matched_songs=0):
    if connection is None:
        print(f"Failed to add playlist data for {playlist_name}")
        return
    execute(connection, f"DELETE FROM playlist_data WHERE time<{int(time())-3600}")
    yt_songs=[]
    sp_songs=[]
    match_list=[]
    nf_list=[]
    for sp in spotify_songs:
        sp_songs.append(prep_sp_song(sp))
    for song in youtube_songs:
        yt_songs.append(prep_song(song))
    for song in matches:
        match_list.append(prep_song(song))
    for song in not_found:
        nf_list.append(prep_song(song))
    query=f"REPLACE INTO playlist_data VALUES ('{token}',{int(time())},'{load_error}',{currently_loading},'{playlist_name}','{json.dumps(yt_songs)}','{json.dumps(sp_songs)}','{json.dumps(match_list)}','{json.dumps(nf_list)}',{total_songs},{scraped_songs},{matched_songs});"
    execute(connection,query)

def get_playlist_data(connection, token):
    query=f'SELECT * FROM playlist_data WHERE user_token="{token}"'
    res=None
    if connection is not None:
        res=read(connection,query)
    if res is None or len(res)==0:
        return ("","",True,"","[]","[]","[]","[]",0,0,0)
    return res[0]

def playlist_is_loading(connection,token):
    if connection is None:
        print(f"Failed to add playlist data for {token}")
        return
    data=get_playlist_data(connection, token)
    if len(data)==0:
        return True
    return bool(data[0][2])

def delete_playlist_data(connection,token):
    if connection is None:
        print(f"Failed to delete playlist data for {token}")
        return
    query=f'DELETE FROM playlist_data WHERE user_token="{token}"'
    execute(connection,query)
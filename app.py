#!/usr/bin/env python

# (c) 2011 Rdio Inc
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import datetime
import json
import os
import sys
import traceback

from discoversong import make_unique_email, generate_playlist_name
from discoversong.db import get_db
from discoversong.forms import EditForm
from discoversong.parse import parse
from discoversong.rdio import get_rdio, get_rdio_and_current_user, get_rdio_with_access

from flask import Flask, request, g, redirect, render_template

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)

@app.before_request
def before_request():
  g.db = get_db()

@app.teardown_request
def teardown_request(exception):
  if exception:
    print exception
  g.db.close()

@app.route('/', methods=['GET', 'POST'])
def root():
    
  rdio, currentUser = get_rdio_and_current_user()
  
  if rdio and currentUser:
    user_id = int(currentUser['key'][1:])
    
    myPlaylists = rdio.call('getPlaylists')['result']['owned']
    
    result = list(g.db.select('discoversong_user', what='address, playlist', where="rdio_user_id=%i" % user_id))
    if len(result) == 0:
      access_token = request.cookies.get('at')
      access_token_secret = request.cookies.get('ats')
      g.db.insert('discoversong_user', rdio_user_id=user_id, address=make_unique_email(currentUser), token=access_token, secret=access_token_secret, playlist='new')
      result = list(g.db.select('discoversong_user', what='address, playlist', where="rdio_user_id=%i" % user_id))[0]
    else:
      result = result[0]
    
    message = ''
    if request.method == 'POST':
      message = '  Saved your selections.'
    
    return render_template('loggedin.html', name=currentUser['firstName'],
                           message=message,
                           to_address=result['address'],
                           playlists=myPlaylists,
                           selected=result['playlist']
                          )
  else:
    return render_template('loggedout.html')

@app.route('/login', methods=['GET'])
def login():
  
  # clear all of our auth cookies
  # begin the authentication process
  rdio = get_rdio()
  
  url = rdio.begin_authentication(callback_url = 'http://discoversong.com/callback')
  # save our request token in cookies
  # go to Rdio to authenticate the app
  response = redirect(url)
  
  response.set_cookie('at', '', expires=-1)
  response.set_cookie('ats', '', expires=-1)
  response.set_cookie('rt', '', expires=-1)
  response.set_cookie('rts', '', expires=-1)
  response.set_cookie('rt', rdio.token[0], expires=60*60*24) # expires in one day
  response.set_cookie('rts', rdio.token[1], expires=60*60*24) # expires in one day
  
  return response

@app.route('/callback', methods=['GET'])
def callback():
  
  # get the state from cookies and the query string
  request_token = request.cookies.get('rt')
  request_token_secret = request.cookies.get('rts')
  verifier = request.form['oauth_verifier']
  # make sure we have everything we need
  if request_token and request_token_secret and verifier:
    response = redirect('/')

    # exchange the verifier and request token for an access token
    rdio = get_rdio_with_access(request_token, request_token_secret)
    rdio.complete_authentication(verifier)
    # save the access token in cookies (and discard the request token)
    response.set_cookie('at', rdio.token[0], expires=60*60*24*14) # expires in two weeks
    response.set_cookie('ats', rdio.token[1], expires=60*60*24*14) # expires in two weeks
    response.set_cookie('rt', '', expires=-1)
    response.set_cookie('rts', '', expires=-1)
    # go to the home page
  else:
    response = redirect('/logout')
  return response

@app.route('/logout', methods=['GET'])
def logout():
  
  response = redirect('/')
  # clear all of our auth cookies
  response.set_cookie('at', '', expires=-1)
  response.set_cookie('ats', '', expires=-1)
  response.set_cookie('rt', '', expires=-1)
  response.set_cookie('rts', '', expires=-1)
  # and go to the homepage
  return response

@app.route('/save', methods=['POST'])
def save():
    
  action = request.form['button']
  
  rdio, currentUser = get_rdio_and_current_user()
  user_id = int(currentUser['key'][1:])
  db = get_db()
  
  if action == 'save':
  
    db.update('discoversong_user', where="rdio_user_id=%i" % user_id, playlist=request.form['playlist'])
  
  return redirect('/?saved=True') 

@app.route('/idsong', methods=['POST'])
def idsong():

  try:
    db = get_db()
    
    envelope = json.loads(request.form['envelope'])
    to_addresses = envelope['to']
    
    print 'received email to', to_addresses
    
    for to_address in to_addresses:
      
      lookup = db.select('discoversong_user', what='rdio_user_id, playlist, token, secret', where="address='%s'" % to_address)
      
      if len(lookup) == 1:
        result = lookup[0]
        
        access_token = str(result['token'])
        access_token_secret = str(result['secret'])
        
        rdio, current_user = get_rdio_and_current_user(access_token=access_token, access_token_secret=access_token_secret)
        
        print 'found user', current_user['username']
        
        subject = request.form['subject']
        
        title, artist = parse(subject)
        
        print 'parsed artist', artist, 'title', title
        
        search_result = rdio.call('search', {'query': ' '.join([title, artist]), 'types': 'Track'})
        
        track_keys = []
        name_artist_pairs_found = {}
        
        for possible_hit in search_result['result']['results']:
          
          if possible_hit['canStream']:
            
            name = possible_hit['name']
            artist_name = possible_hit['artist']
            
            if name_artist_pairs_found.has_key((name, artist_name)):
              continue
            
            name_artist_pairs_found[(name, artist_name)] = True
            
            track_key = possible_hit['key']
            track_keys.append(track_key)
        
        print 'found tracks', track_keys
        
        playlist_key = result['playlist']
        
        if playlist_key in ['new', 'alwaysnew']:
          
          p_names = [playlist['name'] for playlist in rdio.call('getPlaylists')['result']['owned']]

          new_name = generate_playlist_name(p_names)
          
          print 'creating new playlist', new_name
          
          result = rdio.call('createPlaylist', {'name': new_name,
                                                'description': 'Songs found by discoversong on %s.' % datetime.datetime.now().strftime('%A, %d %b %Y %H:%M'),
                                                'tracks': ', '.join(track_keys)})
          new_key = result['result']['key']
          
          if playlist_key == 'new':
            
            print 'setting', new_key, 'as the playlist to use next time'
            
            user_id = int(current_user['key'][1:])
            db.update('discoversong_user', where="rdio_user_id=%i" % user_id, playlist=new_key)
          # else leave 'alwaysnew' to repeat this behavior every time
        
        else:
          rdio.call('addToPlaylist', {'playlist': playlist_key, 'tracks': ', '.join(track_keys)})
        
  except:
    traceback.print_exception(*sys.exc_info())
  
  return None

if __name__ == "__main__":
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port, debug=True)

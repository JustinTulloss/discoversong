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
import web

from discoversong import make_unique_email, generate_playlist_name
from discoversong.db import get_db
from discoversong.forms import editform
from discoversong.parse import parse
from discoversong.rdio import get_rdio, get_rdio_and_current_user, get_rdio_with_access

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

urls = (
  '/', 'root',
  '/login', 'login',
  '/callback', 'callback',
  '/logout', 'logout',
  '/save', 'save',
  '/idsong', 'idsong',
)

app = web.application(urls, globals())

render = web.template.render('templates/')

class root:
  def GET(self):
    
    rdio, currentUser = get_rdio_and_current_user()
    
    if rdio and currentUser:
      user_id = int(currentUser['key'][1:])
      
      myPlaylists = rdio.call('getPlaylists')['result']['owned']
      
      db = get_db()
      
      result = list(db.select('discoversong_user', what='address, playlist', where="rdio_user_id=%i" % user_id))
      if len(result) == 0:
        access_token = web.cookies().get('at')
        access_token_secret = web.cookies().get('ats')
        db.insert('discoversong_user', rdio_user_id=user_id, address=make_unique_email(currentUser), token=access_token, secret=access_token_secret, playlist='new')
        result = list(db.select('discoversong_user', what='address, playlist', where="rdio_user_id=%i" % user_id))[0]
      else:
        result = result[0]
      
      message = ''
      if 'saved' in web.input():
        message = '  Saved your selections.'
      
      return render.loggedin(name=currentUser['firstName'],
                             message=message,
                             to_address=result['address'],
                             editform=editform(myPlaylists, result['playlist'])
                            )
    else:
      return render.loggedout()

class login:
  
  def GET(self):
    # clear all of our auth cookies
    web.setcookie('at', '', expires=-1)
    web.setcookie('ats', '', expires=-1)
    web.setcookie('rt', '', expires=-1)
    web.setcookie('rts', '', expires=-1)
    # begin the authentication process
    rdio = get_rdio()
    url = rdio.begin_authentication(callback_url = web.ctx.homedomain+'/callback')
    # save our request token in cookies
    web.setcookie('rt', rdio.token[0], expires=60*60*24) # expires in one day
    web.setcookie('rts', rdio.token[1], expires=60*60*24) # expires in one day
    # go to Rdio to authenticate the app
    raise web.seeother(url)

class callback:
  
  def GET(self):
    # get the state from cookies and the query string
    request_token = web.cookies().get('rt')
    request_token_secret = web.cookies().get('rts')
    verifier = web.input()['oauth_verifier']
    # make sure we have everything we need
    if request_token and request_token_secret and verifier:
      # exchange the verifier and request token for an access token
      rdio = get_rdio_with_access(request_token, request_token_secret)
      rdio.complete_authentication(verifier)
      # save the access token in cookies (and discard the request token)
      web.setcookie('at', rdio.token[0], expires=60*60*24*14) # expires in two weeks
      web.setcookie('ats', rdio.token[1], expires=60*60*24*14) # expires in two weeks
      web.setcookie('rt', '', expires=-1)
      web.setcookie('rts', '', expires=-1)
      # go to the home page
      raise web.seeother('/')
    else:
      # we're missing something important
      raise web.seeother('/logout')
    
class logout:
  
  def GET(self):
    # clear all of our auth cookies
    web.setcookie('at', '', expires=-1)
    web.setcookie('ats', '', expires=-1)
    web.setcookie('rt', '', expires=-1)
    web.setcookie('rts', '', expires=-1)
    # and go to the homepage
    raise web.seeother('/')

class save:
    
  def GET(self):
    
    action = web.input()['button']
    
    rdio, currentUser = get_rdio_and_current_user()
    user_id = int(currentUser['key'][1:])
    db = get_db()
    
    if action == 'save':
    
      db.update('discoversong_user', where="rdio_user_id=%i" % user_id, playlist=web.input()['playlist'])
      
    raise web.seeother('/?saved=True') 

class idsong:

  def POST(self):
    try:
      db = get_db()
      
      envelope = json.loads(web.input()['envelope'])
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
          
          subject = web.input()['subject']
          
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
      
      print web.rawinput('POST')
    
    return None

if __name__ == "__main__":
    app.run()

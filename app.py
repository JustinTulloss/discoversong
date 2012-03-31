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

# include the parent directory in the Python path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# import the rdio-simple library
from rdio import Rdio

import web

import urllib2

from includes import *

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

class discoversong:

  @staticmethod
  def generate_name():
    import random
    name = ''
    for i in range(10):
      name += letters[random.randrange(0, len(letters))]
      name += str(random.randrange(0, 9))
    name += '@discoversong.com'
    return name
  
  @staticmethod
  def make_unique_email(db):
    
    exists = 1
    name = None
    
    while exists > 0:
      name = discoversong.generate_name()
      exists = db.select('discoversong_user', what='count(*)', where="address='%s'" % name)[0]['count']
    
    return name
  
  @staticmethod
  def get_rdio():
    return Rdio((os.environ['RDIO_CONSUMER_KEY'], os.environ['RDIO_CONSUMER_SECRET']))
  
  @staticmethod
  def get_rdio_with_access(token, secret):
    return Rdio((os.environ['RDIO_CONSUMER_KEY'], os.environ['RDIO_CONSUMER_SECRET']), (token, secret))
  
  @staticmethod
  def get_rdio_and_current_user(access_token=NOT_SPECIFIED, access_token_secret=NOT_SPECIFIED):
      
    if access_token == NOT_SPECIFIED:
      access_token = web.cookies().get('at')
    if access_token_secret == NOT_SPECIFIED:
      access_token_secret = web.cookies().get('ats')
    
    if access_token and access_token_secret:
  
      rdio = discoversong.get_rdio_with_access(access_token, access_token_secret)
      # make sure that we can make an authenticated call
    
      try:
        currentUser = rdio.call('currentUser')['result']
      except urllib2.HTTPError:
        # this almost certainly means that authentication has been revoked for the app. log out.
        raise web.seeother('/logout')
      
      return rdio, currentUser
    
    else:
      
      return None, None
  
  @staticmethod
  def get_db():
  
    dburl = os.environ['HEROKU_SHARED_POSTGRESQL_JADE_URL']
    
    db = web.database(dburl=dburl,
                      dbn='postgres',
                      host='pg60.sharedpg.heroku.com',
                      user='tguaspklkhnrpn',
                      pw='4KBnjLB1n5wbuvzNB4p7DyQEpF',
                      db='vivid_winter_30977')
    return db
  
  @staticmethod
  def parse_vcast(subject):
    
    lead = 'Music ID: "'
    separator = '" by '
    
    if subject.find(lead) < 0 or subject.find(separator) < 0:
      raise ValueError('not VCast!')
    
    title_start = subject.find(lead) + len(lead)
    title_end = subject.find(separator)
    
    title = subject[title_start:title_end]
    
    artist_start = title_end + len(separator)
    
    artist = subject[artist_start:]
  
    return title, artist
  
  @staticmethod
  def parse_shazam(subject):
    
    separator =  '- '
    
    title_end = subject.find(separator)
    if title_end < 0:
      raise ValueError('not Shazam!')
    
    title = subject[:title_end]
    
    artist_start = title_end + len(separator)
    artist = subject[artist_start:]
    return title, artist
  
  @staticmethod
  def parse_unknown(subject):
    
    return subject, ''
  
  @staticmethod
  def parse(subject):
    
    parsers = [discoversong.parse_vcast,
               discoversong.parse_shazam,
               discoversong.parse_unknown] # this should always be last
    
    for parse in parsers:
      try:
        parsed = parse(subject)
        return parsed
      except:
        continue
    raise ValueError('at least the unknown parser should have worked!')
  
  @staticmethod
  def get_editform(playlists, selected):
    from web import form
    
    editform = form.Form(
        form.Dropdown(name='playlist_key', description='Playlist to save songs to', value=selected, args=[(playlist['key'], playlist['name']) for playlist in playlists]),
        form.Button('or create a new playlist', value='new'),
        form.Button('Save', value='save'),
    )
    
    return editform()

class root:
  def GET(self):
    
    rdio, currentUser = discoversong.get_rdio_and_current_user()
    
    if rdio and currentUser:
      user_id = int(currentUser['key'][1:])
      
      myPlaylists = rdio.call('getPlaylists')['result']['owned']
      
      db = discoversong.get_db()
      
      result = list(db.select('discoversong_user', what='address, playlist', where="rdio_user_id=%i" % user_id))
      if len(result) == 0:
        access_token = web.cookies().get('at')
        access_token_secret = web.cookies().get('ats')
        db.insert('discoversong_user', rdio_user_id=user_id, address=discoversong.make_unique_email(db), token=access_token, secret=access_token_secret)
        result = list(db.select('discoversong_user', what='address, playlist', where="rdio_user_id=%i" % user_id))[0]
      else:
        result = result[0]
      
      message = ''
      if 'saved' in web.input():
        message = '  Saved your selections.'
      
      return render.loggedin(name=currentUser['firstName'],
                             message=message,
                             to_address=result['address'],
                             editform=discoversong.get_editform(myPlaylists, result['playlist'])
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
    rdio = discoversong.get_rdio()
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
      rdio = discoversong.get_rdio_with_access(request_token, request_token_secret)
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
    print web.input().keys()
    
    rdio, currentUser = discoversong.get_rdio_and_current_user()
    user_id = int(currentUser['key'][1:])
    
    db = discoversong.get_db()
    
    db.update('discoversong_user', where="rdio_user_id=%i" % user_id, playlist=web.input()['playlist'])
    
    raise web.seeother('/?saved=True') 

class idsong:

  def POST(self):
    db = discoversong.get_db()

    to_address = web.input()['to']
    print web.input()['from'], web.input().keys(), web.input()['plain']
    
    result = db.select('discoversong_user', what='rdio_user_id, playlist, token, secret', where="address='%s'" % to_address)[0]
    
    access_token = str(result['token'])
    access_token_secret = str(result['secret'])
    
    playlist_key = result['rdio_playlist_key']

    rdio, current_user = discoversong.get_rdio_and_current_user(access_token=access_token, access_token_secret=access_token_secret)
    
    subject = web.input()['subject']
    
    title, artist = discoversong.parse(subject)
    
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
    
    rdio.call('addToPlaylist', {'playlist': playlist_key, 'tracks': ', '.join(track_keys)})
    
    return None

if __name__ == "__main__":
    app.run()

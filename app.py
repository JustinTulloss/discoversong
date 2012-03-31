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
# and our example credentials
from rdio_consumer_credentials import *

# import web.py
import web

import urllib2

urls = (
  '/', 'root',
  '/login', 'login',
  '/callback', 'callback',
  '/logout', 'logout',
  '/save', 'save',
  '/idsong', 'idsong',
)
app = web.application(urls, globals())

letters = 'abcdefghijklmnopqrstuvwxyz'
numbers = '1234567890'
def make_unique_email(db):
  assert db != None
  return '61212cf0152d9aff08a7@cloudmailin.net'
  #import random
  #name = ''
  #for i in range(15):
  #  name += letters[random.randrange(0, len(letters))]
  #  name += numbers[random.randrange(0, len(numbers))]
  #exists = db.select('discoplay_user', what='count(*)', where="email_to_address='%s'" % name)[0]
  #if exists['count'] > 0:
  #  return make_unique_email(db)
  #else:
  #  return name

NOT_SPECIFIED = object()

def get_rdio_and_current_user(access_token=NOT_SPECIFIED, access_token_secret=NOT_SPECIFIED):
    
  if access_token == NOT_SPECIFIED:
    access_token = web.cookies().get('at')
  if access_token_secret == NOT_SPECIFIED:
    access_token_secret = web.cookies().get('ats')
  
  if access_token and access_token_secret:

    rdio = Rdio((RDIO_CONSUMER_KEY, RDIO_CONSUMER_SECRET),
      (access_token, access_token_secret))
    # make sure that we can make an authenticated call
  
    try:
      currentUser = rdio.call('currentUser')['result']
    except urllib2.HTTPError:
      # this almost certainly means that authentication has been revoked for the app. log out.
      raise web.seeother('/logout')
    
    return rdio, currentUser
  
  else:
    
    return None, None
  
def get_db():
  
  dburl = os.environ['HEROKU_SHARED_POSTGRESQL_JADE_URL']
  
  db = web.database(dburl=dburl,
                    dbn='postgres',
                    host='pg60.sharedpg.heroku.com',
                    user='tguaspklkhnrpn',
                    pw='4KBnjLB1n5wbuvzNB4p7DyQEpF',
                    db='vivid_winter_30977')
  return db

class root:
  def GET(self):
    
    rdio, currentUser = get_rdio_and_current_user()
    
    if rdio and currentUser:
      user_id = int(currentUser['key'][1:])
      
      myPlaylists = rdio.call('getPlaylists')['result']['owned']
      
      db = get_db()
      
      result = list(db.select('discoplay_user', what='email_from_address, email_to_address, rdio_playlist_id', where="rdio_user_id=%i" % user_id))
      if len(result) == 0:
        access_token = web.cookies().get('at')
        access_token_secret = web.cookies().get('ats')
        db.insert('discoplay_user', rdio_user_id=user_id, email_from_address=None, email_to_address=make_unique_email(db), rdio_playlist_id=0, access_token=access_token, access_token_secret=access_token_secret)
        result = list(db.select('discoplay_user', what='email_from_address, email_to_address, rdio_playlist_id', where="rdio_user_id=%i" % user_id))[0]
      else:
        result = result[0]
      
      message = ''
      if 'saved' in web.input():
        message = '  Saved your selections.'

      response = '''
      <html><head><title>Discoplay</title></head><body>
      Welcome %s!%s
      ''' % (currentUser['firstName'], message)
      
      response += '''<form action="/save">
        <table border=0>
        <tr><th>Send Song ID emails to</th><th>Discoplay expects emails from</th><th>Playlist to save to</th><th>Save</th></tr>
        <tr><td>%s</td><td><input type="text" name="fromemail" value="%s"/></td><td><select name="playlist_id">%s</select></td><td><input type="submit" name="save" value="Save"/></td></tr>
      </form>''' % (result['email_to_address'], result['email_from_address'], ''.join(['<option value=%i %s>%s</option>' % (int(playlist['key'][1:]), 'selected=True' if int(playlist['key'][1:]) == result['rdio_playlist_id'] else '', playlist['name']) for playlist in myPlaylists]))

      response += '''<a href="/logout">Log out of Rdio</a></body></html>'''
      return response
    else:
      return '''
      <html><head><title>Discoplay</title></head><body>
      <a href="/login">Log into Rdio</a>
      </body></html>
      '''

class login:
  def GET(self):
    # clear all of our auth cookies
    web.setcookie('at', '', expires=-1)
    web.setcookie('ats', '', expires=-1)
    web.setcookie('rt', '', expires=-1)
    web.setcookie('rts', '', expires=-1)
    # begin the authentication process
    rdio = Rdio((RDIO_CONSUMER_KEY, RDIO_CONSUMER_SECRET))
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
      rdio = Rdio((RDIO_CONSUMER_KEY, RDIO_CONSUMER_SECRET),
        (request_token, request_token_secret))
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
    
    rdio, currentUser = get_rdio_and_current_user()
    user_id = int(currentUser['key'][1:])
    
    db = get_db()
    
    db.update('discoplay_user', where="rdio_user_id=%i" % user_id, email_from_address=web.input()['fromemail'], rdio_playlist_id=int(web.input()['playlist_id']))
    
    raise web.seeother('/?saved=True') 

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

def parse_shazam(subject):
  separator =  '- '
  
  title_end = subject.find(separator)
  title = subject[:title_end]
  
  artist_start = title_end + len(separator)
  artist = subject[artist_start:]
  return title, artist

class idsong:

  def POST(self):
    db = get_db()

    from_address = web.input()['from']
    print web.input()['plain']
    
    result = db.select('discoplay_user', what='rdio_user_id, rdio_playlist_id, access_token, access_token_secret', where="email_from_address='%s'" % from_address)[0]
    
    access_token = str(result['access_token'])
    access_token_secret = str(result['access_token_secret'])
    
    playlist_key = 'p%i' % result['rdio_playlist_id']

    rdio, current_user = get_rdio_and_current_user(access_token=access_token, access_token_secret=access_token_secret)
    
    subject = web.input()['subject']
    
    try:
      title, artist = parse_vcast(subject)
      print 'vcast parsed', title, artist
    except:
      title, artist = parse_shazam(subject)
      print 'shazam parsed', title, artist
    
    search_result = rdio.call('search', {'query': ' '.join([title, artist]), 'types': 'Track'})
    
    track_keys = []
    for possible_hit in search_result['result']['results']:
      
      if possible_hit['canStream']:
        
        track_key = possible_hit['key']
        track_keys.append(track_key)
    
    rdio.call('addToPlaylist', {'playlist': playlist_key, 'tracks': ', '.join(track_keys)})
    
    return None

if __name__ == "__main__":
    app.run()

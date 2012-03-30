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
import random
import sys,os.path
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
  '/savefromemail', 'savefromemail',
)
app = web.application(urls, globals())

letters = 'abcdefghijklmnopqrstuvwxyz'
numbers = '1234567890'
def make_unique_email(db):
  name = ''
  for i in range(15):
    name += letters[random.randrange(0, len(letters))]
    name += numbers[random.randrange(0, len(numbers))]
  exists = db.select('discoplay_user', what='count(*)', where="email_to_address='%s'" % name)[0]
  if exists['count'] > 0:
    return make_unique_email(db)
  else:
    return name

class root:
  def GET(self):
    access_token = web.cookies().get('at')
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
      
      user_id = int(currentUser['key'][1:])
      
      myPlaylists = rdio.call('getPlaylists')['result']['owned']
      
      dburl = os.environ['HEROKU_SHARED_POSTGRESQL_JADE_URL']
      db = web.database(dburl=dburl,
          dbn='postgres', host='pg60.sharedpg.heroku.com', user='tguaspklkhnrpn', pw='4KBnjLB1n5wbuvzNB4p7DyQEpF', db='vivid_winter_30977')
      
      result = list(db.select('discoplay_user', what='email_from_address, email_to_address, rdio_playlist_id', where="rdio_user_id=%i" % user_id))
      if len(result) == 0:
        db.insert('discoplay_user', rdio_user_id=user_id, email_from_address=None, email_to_address=make_unique_email(db), rdio_playlist_id=0)
        result = list(db.select('discoplay_user', what='email_from_address, email_to_address, rdio_playlist_id', where="rdio_user_id=%i" % user_id))[0]
      else:
        result = result[0]
      
      response = '''
      <html><head><title>Discoplay</title></head><body>
      Welcome %s!
      ''' % currentUser['firstName']
      
      response += '''<form action="/savefromemail">
        <table border=0>
        <tr><th>Send Song ID emails to</th><th>Discoplay expects emails from</th><th>Playlist to save to</th><th>Save</th></tr>
        <tr><td>%s</td><td><input type="text" name="fromemail"/></td><td><select name="playlist_id">%s</select></td><td><input type="submit" name="save" value="Save"/></td></tr>
      </form>''' % (result['email_to_address'], ''.join(['<option value=%i>%s</option>' % (int(playlist['key'][1:]), playlist['name']) for playlist in myPlaylists]))

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

class savefromemail:
  def POST(self):
    return 'something something'
  
if __name__ == "__main__":
    app.run()

import psycopg2

def get_db():

  conn = psycopg2.connect("dbname='vivid_winter_30977' user='tguaspklkhnrpn' host='pg60.sharedpg.heroku.com' password='4KBnjLB1n5wbuvzNB4p7DyQEpF'")

  return conn


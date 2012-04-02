def editform(playlists, selected):
  from web import form
  
  editform = form.Form(
      form.Dropdown(name='playlist',
                    description='Playlist to save songs to',
                    value=selected,
                    args=[(playlist['key'], playlist['name']) for playlist in playlists]),
      form.Button('button', value='new', html='or create a new playlist'),
      form.Button('button', value='save', html='Save'),
  )
  
  return editform()
    

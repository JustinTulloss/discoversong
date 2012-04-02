def editform(playlists, selected):
  from web import form
  
  new_playlist = ('new', '*create a new playlist')
  always_new = ('alwaysnew', '*always create a new playlist')
  playlist_options = [(playlist['key'], playlist['name']) for playlist in playlists]
  args = [new_playlist, always_new]
  args.extend(playlist_options)
  
  editform = form.Form(
      form.Dropdown(name='playlist',
                    description='Playlist to save songs to',
                    value=selected,
                    args=args),
      form.Button('button', value='new', html='or create a new playlist'),
      form.Button('button', value='save', html='Save'),
  )
  
  return editform()
    

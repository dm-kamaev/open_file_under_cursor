import sublime, sublime_plugin
import os.path, string
import re # regexp
import json

VALID_FILENAME_CHARS = "-_.() %s%s%s" % (string.ascii_letters, string.digits, "/\\")
filename_re = re.compile(r'[\w/\.@-]+')

reg_exp_file_extension = re.compile('(\.\w+)$') # file extension

reg_exp_filename_with_start_dog = re.compile('^@') # for webpack and other

reg_exp_express_poll_client = re.compile('^\/p\/express_poll\/client') # if /p/express_poll

# важно что имя функции должно заканчиваться на Command
# и совпадать с именем в key bindings user, только там пишется snake case
class OpenFileUnderCursorCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        for region in self.view.sel():
            # Find anything looking like file in whole line at cursor
            whole_line = self.view.substr(self.view.line(region))
            row, col = self.view.rowcol(region.begin())
            while col >= len(whole_line) or whole_line[col] in VALID_FILENAME_CHARS:
                col -= 1
            m = filename_re.search(whole_line, col)

            # print("Debug import or require '%s'" % (whole_line))

            # syntax = self.view.settings().get('syntax'); # like: Packages/Babel/JavaScript (Babel).sublime-syntax
            # sublime.status_message(syntax)
            # print(syntax)

            # {
            #     'platform': 'OSX',
            #     'file_path': '/p/express_poll/client/services',
            #     'packages': '/Users/mitya/Library/Application Support/Sublime Text 3/Packages',
            #     'file': '/p/express_poll/client/services/ApiService.js',
            #     'file_name': 'ApiService.js',
            #     'file_base_name': 'ApiService',
            #     'folder': '/p',
            #     'file_extension': 'js'
            # }
            extract_variables = self.view.window().extract_variables()
            file_path = extract_variables.get('file_path')
            # active file
            opened_file = self.view.window().active_view().file_name()

            if m:
                filename = m.group()
                # print("=== Opening file '%s'" % (filename))
                # open file as @/base/createRequester.js
                if reg_exp_filename_with_start_dog.search(filename):
                  path = Maybe_search_path_via_alias().search(filename, opened_file)
                  if path is None:
                    print('### Nothing found for path "'+ filename+'"')
                    return
                  self.view.window().open_file(path)
                # open file as 'mysql', 'mysql/index.js'
                elif re.compile('^[^\.@/]').search(filename):
                  path = May_be_file_in_node_modules().search(filename, opened_file)
                  if path is None:
                    print('### Nothing found for path "'+ filename+'"')
                    return
                  self.view.window().open_file(path)
                # open file as './a.js' || '../folder/a.js'
                elif reg_exp_file_extension.search(filename):
                  self.view.window().open_file(filename)
                # open file as './a' || './folder'(via index.js || index.json || index.ts)
                else:
                  path = Maybe_relative_path().search(filename, file_path)
                  if path is None:
                    print('### Nothing found for path "'+ filename+'"')
                    return
                  self.view.window().open_file(path)
            else:
                sublime.status_message("No filename discovered")


"""Search into .baberc, part module-resolver with part alias, replace alias to real path"""
class Maybe_search_path_via_alias:

  def search(self, path_for_open, opened_file):
    aliases = self.__search_aliases(opened_file);
    if aliases is None:
      return None

    # WORK FOR ONLY UNIX, MAC OS, becuase windows use \ for seaparate file
    # get prefix as @
    prefix = path_for_open.split('/')[0]

    if aliases.get(prefix) is None:
      return None

    path_for_open = path_for_open.replace(prefix, aliases.get(prefix), 1)
    return search_extension_for_file_or_index_file(path_for_open)

  """ rescusrive search file '.babelrc' and find aliases in it """
  """ current_path - absolute path to file or folder """
  """ deep - for check depth recursive """
  """ return None or { '@': '/p/client_block_sitemap' } """
  def __search_aliases(self, current_path = None, deep = 100):
    if deep <= 0:
      return None;

    current_folder = '';
    if os.path.isfile(current_path):
      current_folder = os.path.dirname(os.path.normpath(current_path))
    else:
      current_folder = current_path

    list_files = os.listdir(current_folder);

    for el in list_files:
      if el == '.babelrc':
        f = open(os.path.join(current_folder, el), "r")
        content = f.read()
        f.close()
        try:
          babelrc = json.loads(content)
        except Exception as err:
          print('### Not valid json in ".babelrc"  = ', err)
          return None;
        else:
          aliases = self.__find_aliases_in_babelrc(babelrc, current_folder)
          return aliases;

    # get parent folder
    current_folder = os.path.abspath(os.path.join(current_folder, '..'))

    return self.__search_aliases(current_folder, deep - 1)


  """ babelrc is object - { '@': './' } """
  """ current_dir is string - '/p/client_block_sitemap' """
  """ return None or { '@': '/p/client_block_sitemap' } """
  def __find_aliases_in_babelrc(self, babelrc, current_dir):
    if 'plugins' in babelrc is False:
      return None

    for el in babelrc.get('plugins'):
      if el[0] == 'module-resolver':
        aliases = el[1].get('alias')
        for key, path in aliases.items():
          if path == './':
            path = current_dir
          aliases[key] = path
        return aliases

    return None;




"""Search file into folder node_modules"""
class May_be_file_in_node_modules:

  def __init__(self):
    self.regexp_for_node_modules = re.compile("/node_modules$")

  """path_for_open string -  'mysql' || 'mysql/index.js'"""
  """opened_file string -  '/Users/mitya/Desktop/Start/open_file_under_cursor/a/b/c/test.txt' """
  """return None || string - path to file """
  def search(self, path_for_open, opened_file):
    path_node_modules = self.__search_path_to_node_modules(opened_file)
    path = os.path.abspath(os.path.join(path_node_modules, path_for_open))

    if path is None:
      return None

    # if full path to file *.js || *.json and etc
    if re.compile('\/.+\..+$').search(path):
      return path
    else:
      for filename in [ 'index.js', 'index.json', path_for_open+'.js', 'index.ts' ]:
        full_path = os.path.abspath(os.path.join(path, filename))
        if os.path.isfile(full_path):
          return full_path
      return None

  """ recusive search folder for node_modules/ """
  """ current_path string - path to file or folder """
  """ deep string - for control search depth """
  def __search_path_to_node_modules(self, current_path = None, deep = 100):
    if deep <= 0:
      return None;

    current_folder = '';
    if os.path.isfile(current_path):
      current_folder = os.path.dirname(os.path.normpath(current_path))
    else:
      current_folder = current_path

    list_folders = get_list_folders(current_folder);

    for el in list_folders:
      if not (self.regexp_for_node_modules.search(el) is None):
        return os.path.join(current_folder, el)

    current_folder = os.path.abspath(os.path.join(current_folder, '..'))
    return self.__search_path_to_node_modules(current_folder, deep - 1)


""" Search file via reltive path: '../modlue/a.js' || './node_modules/mysql' """
class Maybe_relative_path:
  """path_for_open string -  '../modlue/a.js' || './node_modules/mysql' """
  """file_path_for_opened_file string (relative to which file to look for path) -  '/p/express_poll/folder' """
  """return None || string - path to file """
  def search(self, path_for_open, file_path_for_opened_file):
    path = os.path.abspath(os.path.join(file_path_for_opened_file, path_for_open))

    return search_extension_for_file_or_index_file(path)


def get_list_folders(folder):
  subfolders = []
  for p in os.listdir(folder):
    fullpath = os.path.abspath(os.path.join(folder, p))
    if os.path.isdir(fullpath):
      subfolders.append(fullpath)

  return subfolders


""" if file hasn't extenstion then we try adding extension, if not found, then we checking may be is path to folder and try adding 'index.*' file  """
""" path string -- path without '/path/modules/test' """
""" return None || string -- path without '/path/modules/test.js' || '/path/modules/test.json' """
def search_extension_for_file_or_index_file(file_path):
  if re.compile('\/.+\..+$').search(file_path):
    return file_path

  for extension in [ '.json', '.js', '.ts' ]:
    temp_file_path = file_path+extension
    if os.path.isfile(temp_file_path):
      return temp_file_path

  if os.path.isdir(file_path):
    for filename in [ 'index.json', 'index.js', 'index.ts' ]:
      full_path = os.path.abspath(os.path.join(file_path, filename))
      if os.path.isfile(full_path):
        return full_path

  return None

# Правильный пример
# import sublime, sublime_plugin

# class DecToHexCommand(sublime_plugin.TextCommand):
#   MAX_STR_LEN = 10
#   def run(self, edit):
#     v = self.view

#     # Получаем значение первого выделенного блока
#     dec = v.substr(v.sel()[0])

#     # Заменяем десятичное число шестнадцатеричным или выводим сообщение об ошибке
#     if dec.isdigit():
#       v.replace(edit, v.sel()[0], hex(int(dec))[2:].upper())
#     else:
#       # Обрезаем слишком длинные строки, которые не поместятся в статусбар
#       if len(dec) > self.MAX_STR_LEN:
#         logMsg = dec[0:self.MAX_STR_LEN]+ "..."
#       else:
#         logMsg = dec
#       sublime.status_message("\"" + logMsg + "\" isn't a decimal number!")

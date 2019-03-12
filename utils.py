import time, json, re, unicodedata, codecs
import lxml.html, os, shutil, requests
from requests.utils import quote
from urllib.parse import urljoin
from lxml.etree import strip_elements
from datetime import datetime
import functools
from subprocess import Popen, PIPE
import os, sys, psutil
from multiprocessing import Process
from ftfy import fix_encoding

class LoggingStream:
    def __init__(self,stream,path):
        self.stream = stream
        self.path   = path
    def flush(self):
        self.stream.flush()
    def write(self,data):
        self.stream.write(data)
        try:
            lines = list(filter(lambda s: s, str(data).split('\n')))
            msg = ['%s\t%s\n' % (datetime.now().isoformat(),line) for line in lines]
            with open(self.path,'a') as log:
                log.writelines(msg)
        except Exception as ex:
            self.stream.write(ex)


def logging(func):
    @functools.wraps(func)
    def wrapper_logging(*args, **kwargs):
        sys.stdout = LoggingStream(sys.stdout,func.__name__+'.log')
        stderr, sys.stderr = sys.stderr, sys.stdout
        func(*args, **kwargs)
        sys.stdout, sys.stderr = sys.stdout.stream, stderr
    return wrapper_logging

def check_overheat(pid, pause_temp=95,resume_temp=85,delay=5,echo=True):
    waiting = False
    try:
        p = psutil.Process(pid)
        while True:
            time.sleep(delay)
            temp = get_temp()
            if waiting:
                if temp < resume_temp:
                    p.resume()
                    waiting = False
            else:
                if temp > pause_temp:
                    if echo:
                        print("OVERHEAT: %f" % temp)
                    p.suspend()
                    waiting = True
    except Exception as ex:
        print(ex)

def heatcontrol(func):
    @functools.wraps(func)
    def wrapper_heatcontrol(*args, **kwargs):
        p = Process(target=func,args=args)
        p.start()
        heat_ctrl = Process(target=check_overheat, args=(p.pid,))
        heat_ctrl.start() 
        heat_ctrl.join()
        p.terminate()
        p.join()
    return wrapper_heatcontrol


def execute(command, echo=True):
    p   = Popen(command,shell=True,bufsize=256,stdout=PIPE).stdout
    out = p.read().decode('utf-8')[:-1]
    p.close()
    if echo:
        print(out)
    return out


def get_temp():
  p=Popen('echo $(sensors | grep -o "Core.*:\s*.*(")', shell=True, bufsize=512, stdout=PIPE).stdout
  temps=re.findall("[0-9]+.[0-9]+",p.read().decode('utf-8'))
  p.close()
  temps=[float(s) for s in temps]
  temps=list(map(lambda s:float(s),temps))
  temps=list(filter(lambda s:s<100.0, temps))
  return max(temps)


def echo_and_log(msg,path=__name__+'.log'):
   msg = '\n'.join(['%s\t%s' % (datetime.now().isoformat(),line) for line in msg.split('\n')])
   print(msg)
   with open(path,'a') as f:
     f.write(msg+'\n')
    

def echo(func):
    @functools.wraps(func)
    def wrapper_echo(*args, **kwargs):
        print(func.__name__)
        return func(*args, **kwargs)
    return wrapper_echo

def merge_company(a,b):
    return merge_dicts(a,b,identity_keys=["name","mail","website","kariyer-net-profile"])

def merge_dicts(a,b,identity_keys=[]):
    identity = False
    if identity_keys == "all":
        identity_keys = list(a.keys()) + list(b.keys())
    for key in identity_keys:
        if not (key in a.keys() and key in b.keys()):
            continue
        if type(a[key]) == list or type(b[key]) == list:
            cond = set(as_list(a[key])).intersection(set(as_list(b[key])))
        else:
            cond = a[key] == b[key]
        if cond:
            identity = True
            break
    if not identity:
        return None
    result = {**a,**b}
    for key, value in a.items():
        if key in b.keys() and not key in identity_keys:
            if type(value) == dict:
                result[key] = merge_dicts(a[key],b[key])
            else:
                result[key] = list(set(as_list(b[key]) + as_list(a[key])))
    return result

def clean_dict(e, dirty_values=("",None,[]), recursive=True):
    if e in dirty_values:
        return e
    result = {**e}
    for key,value in e.items():
        if value in dirty_values:
            result.pop(key)
        elif recursive and type(value) == list:
            for item in value:
                if item in dirty_values:
                    result[key].remove(item)
        elif recursive and type(value) == dict:
            result[key] = clean_dict(value)
    return result

def as_list(e):
    if type(e) is str:
        return [e]
    if not e:
        return []
    try:
        return list(e)
    except Exception:
        return [e]

def normalize_mail(url):
    try:
        return re.match(Mail.pattern,url).group().split('?')[0].replace('[at]','@')
    except Exception:
        return ''

def normalize_url(url,root='https://'):
    try:
        url = url.strip()
        if re.match(r'javascript:.*',url):
            return ''
        if url[0] == '#':
            url = ''
        if re.match(r'www\..+',url):
            base = 'https://'
        elif not re.match(r'https+://.+',url):
            base = root
        else:
            base = ''
        return urljoin(base,url)
    except Exception:
        return ''

def normalize_name(name):
    name = asciify(name)
    name = name.lower().strip()
    non_alphanum = r'[^a-zA-Z0-9]+'
    name = re.sub(non_alphanum, '_', name)
    return name.strip('_')
    
def asciify(s):
    s = fix_encoding(s)
    try:    
        return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('utf-8')
    except Exception:
        return ''

def htmlify(s):
    return '<!DOCTYPE html>\n<html><head></head><body>'+s+'</body></html>'

def read_json(json_path):
    try:
        with open(json_path,"r") as f:
            data = json.load(f)
    except Exception as ex:
        #print(ex)
        data = {}
    return data

@echo
def write_json(json_path,data):
    try:
        with open(json_path+".backup","w") as dst, open(json_path) as src: dst.write(src.read())
    except Exception as ex:
        print(ex)
    with open(json_path,"w") as f:
        json.dump(data,f, ensure_ascii=False, indent=4)

class Mail:
  pattern_str = r"([a-zA-Z0-9_.+-]+(@|\[at\])[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
  pattern = re.compile(pattern_str)

def is_mail(url):
  return re.search(Mail.pattern,url)


def regex_in_text(element, pattern):
    strip_elements(element,'script','style')
    text = '\n'.join(element.itertext())
    matches = re.findall(pattern, text)
    return [m[0] for m in matches]

def regex_from_xpath(element,xpath,pattern,multi=False):
  try:
    text  = '\n'.join(element.xpath(xpath))
    matches = re.search(pattern, text)
    if multi:
      return [m[0] for m in re.findall(pattern,text)]
    if matches:
      match = matches.group(0)
    else:
      match = ""
  except Exception as ex:
    #print(ex)
    match = ""
  return match

def try_xpath(element,xpath,alt="",index=0):
  try:
    result = element.xpath(xpath)[index]
  except Exception as ex:
    #print(ex)
    result = alt
  return result

def find_repeating_patterns(items, predicate,n=3,recursive=True):
    result = []
    while items:
        item = items.pop()
        if not predicate(item):
            continue
        repeating = []
        for other in items:
            if not predicate(other):
                continue
            distance = compare_lxmls(item,other) 
            if distance < 0.2:
                repeating.append(other)
        if repeating:
            result.append(item)
            result += repeating
    if not result and recursive:
        for item in items:
            result += find_repeating_patterns(item,target)
    if len(result) < n:
        result = []
    return list(set(result))

def find_containers(elements, target='div', predicate=lambda x:x.xpath('//a'),n=3, deep=True):
    containers = []
    while elements:
        element = elements.pop()
        children = element.xpath(target)
        if not children:
            continue
        items = find_repeating_patterns(children,predicate,n,recursive=False)
        if items:
            containers.append((element,items))
        elif deep:
            elements += children
    return containers



@echo
def scrap_mails(website_url):
    print(website_url)
    link_keywords = ["iletisim","contact","bize ulasin"]
    page        = cached_page(website_url)
    links       = page.xpath("//a")
    matches     = regex_in_text(page,Mail.pattern)
    for link in links:
        if any([key in asciify(link.text).lower() for key in link_keywords]):
            contact_url = link.get("href")
            if is_mail(contact_url):
                matches    += as_list(normalize_mail(contact_url))
            else:
                contact_url = normalize_url(contact_url, root=website_url)
                page        = cached_page(contact_url) 
                matches    += as_list(regex_in_text(page,Mail.pattern))
    mails = list(set(matches))
    print(mails)
    if len(mails) == 1:
        mails = mails[0]
    return mails

def cached_page(url):
  if not url:
    return None
  try:
    if not os.path.isdir('cache'):
      os.mkdir('cache')
    cache = os.path.join("cache/", quote(url, safe=''))
  except Exception as ex:
    pass#print(ex)
  try:
    with open(cache,'r') as f:
      source = f.read()
      page   = lxml.html.fromstring(source)
  except Exception:
    with open(cache, 'w') as f:
      try:
        response = requests.get(url)
        print("Request: "+url)
        source   = response.content
        if source:
          try:
            f.write(source.decode('utf-8'))
          except Exception:
            pass
        page = lxml.html.fromstring(source)
      except Exception:
        page = None
  return page


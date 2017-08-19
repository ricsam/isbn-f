from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
import sys
#sys.path.append("/base/data/home/apps/s~isbn-f/2.358226886723190031/")
try:
    from django.utils import simplejson as json
except ImportError:
    import json
import os



class MainHandler(webapp.RequestHandler):
    def URLEncode(self, params):
        encoded = ''
        
        try:
            import urllib
            encoded = urllib.urlencode(params)
        except ImportError:
            from django.utils.http import urlencode
            encoded = urlencode(params)
        
        return encoded

    def GetHTML(self,url,params):
        raw_reply = "error"
        try:
            # If im using Google App Engine online
            from google.appengine.api import urlfetch

            _address = url
            if params:
                _address += self.URLEncode(params)
            
            r = urlfetch.fetch(_address, deadline=600)
            
            raw_reply = r.content
        except:
            # If im on localhost            
            import urllib2
            
            _address = url
            if params:
                _address += self.URLEncode(params)
            
            raw_reply = urllib2.urlopen(_address).read()
            
        return raw_reply

    def MakeQuery(self, isbn):

        from bs4 import BeautifulSoup
        import string
        import re
        
        
        
        # The query params for libris.kb.se search
        params = {'SEARCH_ALL': isbn, 'd':'libris', 'f':'simp', 'spell':'true'}
        url = "http://libris.kb.se/formatQuery.jsp?"
        
        # Get the HTML of the returned search page, on libris.kb.se
        dom = BeautifulSoup(self.GetHTML(url,params))
        
        alerts = dom.findAll('h2', {'class': 'alert'})
        for i in alerts:
            if i:
                if 'gav noll' in i.get_text():
                    return False

        # Grab the <dl></dl> That holds information about the book
        dls = dom.findAll('dl', {'class': 'fullpostlista'})

        # method to check wether string contains showrecord?q which is the url that holds the id for the new query page.
        # This will only be called if the search doesn't redirect to the book page immedieately, AKA. when the search page return multiply results      
        def checkIfIdURL(obj):
            return obj is not None and obj[:12] == "showrecord?q"
        
        # This string will later hold the id of the book page, only if the search page returns more than one result, and doesn't redirect there immedieately
        link_id = ''
        redirect = False
        
        # Check if the dls list/array is empty
        if not dls:
            redirect = True
            
            # Loop through all links on the page, looking for the showrecord?q string in the href attribute
            for link in dom.find_all(href=checkIfIdURL):
                address = link.get('href')
                
                # check wether the first 12 letters match the showrecord?q string
                # the URLs looks like this: http://libris.kb.se/showrecord?q=ghost&r=&n=3&id=8954328&g=&f=simp&s=r&t=v&m=10&d=libris
                # We want to grab the id, id=8954328
                if address[0:12] == "showrecord?q":
                    address_part = address.split('?')
                    address_part = address_part[1].split('&')
                    address_part = address_part[3].split('=')
                    newurl_fragment = address_part[1]
                    
                    # If there are many links on the page then only add the first id
                    if not link_id:
                        link_id = newurl_fragment # id is, in this example, 8954328
            
            # This is the new direct URL to the book
            url = "http://libris.kb.se/bib/" + link_id
    
    
        # If redirect is true we need to fetch the new DOM from the new page. We don't want the old search result page.
        if redirect == True:
            dom = BeautifulSoup(self.GetHTML(url,None))
            
            # Grab the new <dl></dl>
            dls = dom.findAll('dl', {'class': 'fullpostlista'})
        
        
        
        h1 = dom.find('h1')
        
        
        # Get the author(s)
        authors = []
        
        # All the authors on the page are bold, so the authors name will be in either <strong> tags or <dt> tags 
        # with the attribute 'openclose' which also are bold. 
        
        # Loop through all <dt>s with the attribute of 'openclose'
        for i in dom.select('dt.openclose.negindented'):
            #if i
            
            # i is probably something like: <dt class="openclose minus negindented">Werner, Mads, <span class="beskrivning">1952- (forfattare)</span>
            # WARRNING: o width two dots above becomes \xc3\xb6
            # We only want the text content of <dt> tag, which is the first child of the element
            num = 0     
            for t in i.contents:
                
                if num > 0:
                    # This removes the other childs of the <dt> element except for the first one.
                    i.contents[num].extract()
                num += 1        

            # After striping away all the unnecessary child nodes we convert the <dt> tag content to text.
            # We then append it to the authors list which holds all the authors, if there are more that one author.
            authors.append(i.get_text().rstrip())
            
        
        # This loops thorough all the strong tags of the page with a parent <dd> tag. This is to find all the rest of the authors.
        for i in dom.select('dd > strong'):
        
            # The dd tag looks like this. We are grabing the first child, the strong tag, from the dd tag:
            # <dd><strong>Roth, Bengt</strong> <span class="beskrivning">(forfattare)</span></dd>
            authors.append(i.get_text().rstrip())
        
        
        # Loop through all the authors and remove the last , which usually are there.
        num = 0
        for i in authors:
            if ',' in i[-3:]:
                authors[num] = i[:-3] + re.sub(",", '', i[-3:], flags=re.U)
            num += 1
        
        
        tryckeriHTML = ''
        
        # This loops through all text on the page, not the tags, and tries to find a text node that matches, 
        # Lund : Studentlitteratur, 2011 ### And that lies in a <dt> tag.
        for val in dom.strings:
            if not tryckeriHTML and (',' in val or ' : ' in val or 'Publishing' in val) and re.search('[^0-9][0-9]{4}[^0-9]', repr(val)) and val.parent.name == 'dt' and 'kortvyvanster' in ''.join(val.parent.parent.parent.get('class')):
                tryckeriHTML = val
        
        # location will be Lund in the example
        
        separator = ''
        if ' : ' in tryckeriHTML:
            separator = ' : '
        else:
            separator = re.sub(r'([\d|\w|\s])+', '', tryckeriHTML, flags=re.U)
            separator = separator[0:1]

        if separator:
            
            location = tryckeriHTML.split(separator)[0]
            
            # This removes the string that was extracted from it to make it easier later.
            tryckeriHTML = tryckeriHTML.split(separator)[1]
            
            
            # This searches through, Studentlitteratur, 2011 and tries to find a number with the length of 4, AKA. the year
            m = re.search('[0-9]{4}', tryckeriHTML)
            # This grabs the location of the 2011 in the string.
            stringRange = []
            if m:
                stringRange = m.span()
                # This takes out a piece of the string, based on the location that was returned by m.span()
                year = tryckeriHTML[stringRange[0]:stringRange[1]]
            else:
                year = ''

            # The rest of the string is the value for the publisher.
            if stringRange:
                tryckeriHTML = tryckeriHTML[:stringRange[0]]
                # strip away some ,
                if ',' in tryckeriHTML[-3:]:
                    tryckeriHTML = tryckeriHTML[:-3] + re.sub(",", '', tryckeriHTML[-3:], flags=re.U)

            
            publisher = tryckeriHTML

        else:
            year = ''
            location = ''
            publisher = ''

        # Time to grab the title
        # title looks like this: <h1>Ghost : <span>Johan Ekhe (it's actually Ekhe with a apostrof which is \xc3\xa9 in python) och Ulf Lindstrom : mannen bakom Robyn</span></h1>
        
        # We only want the first child node of the <h1> tag so we do exactly as we did on the first author extraction.
        num = 0
        for t in h1.contents:
            if num > 0:
                h1.contents[num].extract()
            num += 1
            
        raw_title = h1.get_text().rstrip()
        title = raw_title
        
        # Grab the isbn
        # There should only be one ISBN on the page so we can loop through all text nodes on the page and look for the isbn.
        # <dt>ISBN 978-91-44-06973-9</dt>
        isbn = ''
        for val in dom.strings:
            if re.search('ISBN', val) and val.parent.name == 'dt':
                isbn = re.sub(r'([^\d|x|X])+', '', val, flags=re.U)
        
        
        
        # cleanup
        
        num = 0
        for i in authors:
            authors[num] = re.sub(r'([^\d\w\s|,|-])+', '', i, flags=re.U) # Removes everything that ain't digit, letter, comma, dash, <space>
            num += 1
        
        def checkIfStringIsEmpty(string):
            return '<strong>(ERROR: Could not find any result. Follow the link bellow and write this part manually)</strong>' if string == ' ' or not string else string
        
        
        
        title = re.sub(r'([^\d\w\s|-|.])+', '', title, flags=re.U) # Removes everything that ain't digit, letter, dash, dot, <space>
        publisher = re.sub(r'([^\w\s|-|.|/|&])+', '', publisher, flags=re.U) # Removes everything that ain't letter, dash, dot, <space>
        year = re.sub(r'([^\d|-])+', '', year, flags=re.U) # Removes everything that ain't number
        location = re.sub(r'([^\w\s|,])+', '', location, flags=re.U) # Removes everything that ain't a letter

        # remove last space.
        bookList= [title, publisher, year, location]
        for i in range(len(bookList)):
            if bookList[i]:
                bookList[i] = bookList[i][:-2] + re.sub(r'([\s|\n|\r])+', '', bookList[i][-2:], flags=re.U)
                bookList[i] = re.sub(r'([\s|\n|\r])+', '', bookList[i][:2], flags=re.U) +  bookList[i][2:]
        

        # Do a last filtering/cleaning
        title = checkIfStringIsEmpty(bookList[0])
        publisher = checkIfStringIsEmpty(bookList[1])
        year = checkIfStringIsEmpty(bookList[2])
        location = checkIfStringIsEmpty(bookList[3])
        
        # join the authors list, separate with , except for the last two ones
        author = ''
        if len(authors) > 2:
            author = ', '.join(authors[:-2]) 
            author += ', '
            author += ' och '.join(authors[-2:])
        elif len(authors) == 2:
            author = ' och '.join(authors)
        elif len(authors) > 0:
            author = authors[0]
        
        author = checkIfStringIsEmpty(author)
            
        
        # This could have been done alot easier but I just wanted to use conditional expressions.
        # If redirect if False then we need to add the parameters to the base of the url.
                    
        url = url if redirect else url + self.URLEncode(params)

        # If the last char of the title is a dot(.) then remove it because it will be added later.
        if title[-1:] == '.':
            title = title[:-1]
                
        # Add italic style to the title
        title = "<i>%s</i>" % title
        
        
        return {'author': author, 'title': title, 'location': location, 'publisher': publisher, 'year': year, 'url': url, 'isbn': isbn}

    def get(self):
    
	self.response.headers['Access-Control-Allow-Origin'] = '*'
	self.response.headers.add_header("Access-Control-Allow-Origin", "*")

        user_agent = self.request.headers.get('User-Agent', '').lower()
        cpass = 'chroddme' in user_agent
        if cpass:
            self.response.out.write("""<!doctype html public "WHU"><meta charset=utf-8><title>ISBN source factory</title><link href='http://fonts.googleapis.com/css?family=Lilita+One' rel='stylesheet' type='text/css'><!--[if gte IE 9]><style type="text/css">.gradient{filter:none}</style><![endif]-->
<link type=text/css rel=stylesheet href=stylesheets/style.css>
<script type="text/hashsync">self.addEventListener('message', function(e){var v = e.data[0];lines = v.split('\\n');var hash = "";for(i in lines){for(n=0;n<e.data[1].length;n++){if(e.data[1][n].ISBN == lines[i]){var str = "{";for(val in e.data[1][n]){str += "\\"" + val + "\\":\\"" + e.data[1][n][val] + "\\",";}str = str.substring(0,str.length-1);str += '}';hash += str;} else {continue;}}}if("#"+hash != location.hash){self.postMessage(hash);}}, false);</script><script type="text/outputmousecheck">self.addEventListener('message', function(e){for(i=0;i<e.data[0].length;i++){if((e.data[1][0] > e.data[0][i][0] && e.data[1][0] < e.data[0][i][0] + e.data[0][i][2]) && (e.data[1][1] > e.data[0][i][1] && e.data[1][1] < e.data[0][i][1] + e.data[0][i][3])){self.postMessage([true,e.data[0][i]]);return;}}self.postMessage([false]);}, false);</script>
<script type=text/javascript>/*<![CDATA[*/addEventListener('load',function(){var b=new window.WebKitBlobBuilder();b.append(document.querySelector('[type="text/hashsync"]').textContent);var url=window.webkitURL.createObjectURL(b.getBlob());window.ww_hashSync=new Worker(url);window.ww_hashSync.addEventListener('message',function(e){window.location.hash=e.data;},false);},false);function sync_hash_to_val(){window.ww_hashSync.postMessage([document.querySelector('textarea').value,window.source_list]);}
addEventListener('hashchange',hash_to_data,false);addEventListener('load',hash_to_data,false);window.source_list=new Array();function isbn_check(n){var c=parseInt(0);for(i=0;i<10;i++){c+=(10-i)*parseInt(n[i]);}
if((c+10)%11===10){return true;}else{var c=parseInt(0);for(i=0;i<13;i++){if(i%2===0)
c+=parseInt(n[i]);else
c+=3*parseInt(n[i]);}
return c%10===0;}}
window.anchor_mouseEvent=[];function hash_to_data(){document.querySelector('.output').innerHTML="<br><b>K&#228;llor</b>"
var ltr=document.createElement('div');ltr.style.textAlign="left";ltr.className="output_textarea";ltr.innerHTML+="Tryckta";var hash_without_hash=location.hash.substring(1,location.hash.length);var len=hash_without_hash.split("}");var ta_lines=document.querySelector('textarea').value.split("\\n");ta_lst_line=ta_lines[ta_lines.length-1];if(typeof ta_lst_line.length<1){ta_lst_line="";}
for(i=0;i<len.length-1;i++){var sc_h=document.createElement('div');sc_h.className="output_textcontent";var json=decodeURIComponent(len[i])+"}";json=JSON.parse(json);var push_arr=true;for(n=0;n<window.source_list.length;n++){if(json.ISBN==window.source_list[n].ISBN){push_arr=false;}}
if(push_arr==true)
source_list.push(json);sc_h.innerHTML+=json.Author+". ";sc_h.innerHTML+=json.Title+". ";sc_h.innerHTML+=json.From+": ";sc_h.innerHTML+=json.Publisher+", ";sc_h.innerHTML+=json.Year+".<br>";ltr.appendChild(sc_h);sc_h.setAttribute('data-url',json.URL);}
document.querySelector('.output').appendChild(ltr);OAML();}
function n_handler(p){var lst=p[p.length-1];for(i=0;i<window.source_list.length;i++){if(window.source_list[i].ISBN==lst){var str="{";for(val in window.source_list[i]){str+="\\"" + val + "\\":\\"" + window.source_list[i][val] + "\\",";}
str=str.substring(0,str.length-1);str+='}';window.location.hash+=str;return;}}
window.window.canv_load_text="Loading...";(function(){var canvasHTML=document.createElement('canvas');document.querySelector('.output').appendChild(canvasHTML);var c=canvasHTML.getContext('2d');var width=document.querySelector('.output').offsetWidth/2;var height="20";c.canvas.width=width;c.canvas.height=height;c.fillStyle="#FBFBFB";c.strokeStyle="#F1780A";c.lineWidth=1;c.fillRect(0,0,width,height);c.strokeRect(0,0,width,height);var plus=0;var tilt=17;function loop(){if(plus>=20){plus=0;}
var run=true;var x=-tilt;c.lineWidth=1;c.fillRect(0,0,width,height);c.strokeRect(0,0,width,height);c.fillStyle="#FBFBFB";c.strokeStyle="#F1780A";while(run){if(x>width+plus)
run=false;c.lineWidth=10;c.lineCap="square";c.beginPath();c.moveTo(x+tilt+plus,0);c.lineTo(x+plus,height);c.stroke();c.closePath();x+=20;}
c.lineWidth=1;c.strokeRect(0,0,width-1,height);c.fillStyle="#FFFFFF";c.strokeStyle="#000000";c.font="20px 'Lilita One', cursive";c.textBaseline="top";c.strokeText(window.window.canv_load_text,width/2-c.measureText('Loading...').width/2,-1);c.fillText(window.window.canv_load_text,width/2-c.measureText('Loading...').width/2,-1);plus+=1;}
window.canv_load_interval=setInterval(loop,25);})()
var x=new XMLHttpRequest();x.open('POST','/',true);x.addEventListener('error',x_error,false);x.addEventListener('load',function(){if(x.readyState==4&&x.status==200){window.location.hash+=x.responseText;window.clearInterval(window.canv_load_interval);}else{x_error();}},false);x.setRequestHeader('Content-type','application/x-www-form-urlencoded');x.send('t=True&c='+lst);}
function x_error(custom){window.window.canv_load_text="ERROR";window.setTimeout(function(){if(typeof window.canv_load_interval!=="undefined")
window.clearInterval(window.canv_load_interval);},26);if(document.querySelector('.hidden-x-error').getAttribute('data-display')==="false"){var error_elm_class='.hidden-x-error';if(typeof custom!=="undefined")
error_elm_class=custom;document.querySelector('.overlay').style.height="100%";document.querySelector('.overlay').style.opacity=1;document.querySelector(error_elm_class).style.height="auto";document.querySelector(error_elm_class).style.opacity=1;document.querySelector('.overlay').setAttribute('data-display','true');document.querySelector(error_elm_class).setAttribute('data-display','true');window.localStorage.setItem('textarea_value',document.querySelector('textarea').value);}}
function setTBValue(){var hash_without_hash=location.hash.substring(1,location.hash.length);var len=hash_without_hash.split("}");var ta_lines=document.querySelector('textarea').value.split("\\n");ta_lst_line=ta_lines[ta_lines.length-1];if(typeof ta_lst_line.length<1){ta_lst_line="";}
for(i=0;i<len.length-1;i++){var sc_h=document.createElement('div');sc_h.className="output_textcontent";var json=decodeURIComponent(len[i])+"}";json=JSON.parse(json);document.querySelector('textarea').value+=json.ISBN+"\\r\\n";}
document.querySelector('textarea').value+=ta_lst_line;}
addEventListener('load',setTBValue,false);/*]]>*/</script>
<div class=hidden-x-error data-display=false>ERROR: Something went wrong. Please reload the page, all data have been saved.<br>Or just <a href="javascript:void(0)" onclick="window.setTimeout(function(){document.querySelector('.hidden-x-error').style.height='0';document.querySelector('.overlay').style.height='0';},2000);document.querySelector('.overlay').style.opacity=0;document.querySelector('.hidden-x-error').style.opacity=0;document.querySelector('.overlay').setAttribute('data-display','false');document.querySelector('.hidden-x-error').setAttribute('data-display','false')">close</a> this window and continue but stuff will maybe not work!</div><div class="nonvalid_isbn hidden-x-error" data-display=false>ERROR: Are you sure that you have typed correctly?<br>Click <a id="isbn_val_error_close_anch_ff" href="javascript:void(0)" style="outline:0" onclick="window.setTimeout(function(){document.querySelector('textarea').focus();},500);window.setTimeout(function(){document.querySelector('.nonvalid_isbn').style.height='0';document.querySelector('.overlay').style.height='0';},2000);document.querySelector('.overlay').style.opacity=0;document.querySelector('.nonvalid_isbn').style.opacity=0;document.querySelector('.overlay').setAttribute('data-display','false');document.querySelector('.nonvalid_isbn').setAttribute('data-display','false')">here</a> to close.</div><div class=overlay data-display=false></div><header><h1>The ISBN source factory</h1></header><nav><ul><li>Home<li id="show_howto" style="border-right:1px solid rgba(0,0,0,0.8)">How to write a source (swedish)</ul></nav><hr><section><h2>Edit</h2><article><p>Write your ISBN numbers in this box, separate the numbres with a new line</p><textarea placeholder="9174240811" pattern="d{10}" required></textarea><br></article></section><section class=output contenteditable><b>K&#228;llor</b></section><section class=output_anchor></section><section class=clear><a href="javascript:void(0)" onclick="if(confirm('Are you sure?')==true){window.location.hash='';document.querySelector('textarea').value=''}">Clear</a></section><footer><p>By Richard Samuelson</p></footer>
<script type=text/javascript>/*<![CDATA[*/window.output_anchor_mouse_location=[];function OAML(){window.output_anchor_mouse_location=[];for(i=0;i<document.getElementsByClassName('output_textcontent').length;i++){var node=document.getElementsByClassName('output_textcontent')[i];var top=node.offsetTop-node.offsetParent.scrollTop;var height=node.offsetHeight+1;var width=node.offsetWidth+40+(height>32?40:0);var left=window.innerWidth/2-10;var curtop=0;var curtopscroll=0;if(node.offsetParent){do{curtop+=node.offsetTop;curtopscroll+=node.offsetParent?node.offsetParent.scrollTop:0;}while(node=node.offsetParent);var top=curtop-curtopscroll;}
window.output_anchor_mouse_location.push([left,top,width,height,i,document.getElementsByClassName('output_textcontent')[i].getAttribute('data-url')]);}}
document.querySelector('.output').addEventListener('scroll',OAML,false);function add_styles(){document.querySelector('article p').style.maxWidth=(innerWidth/2-40).toString()+"px";document.querySelector('.output_anchor').style.height=(innerHeight-20).toString()+"px";document.querySelector('.output').style.height=(innerHeight-20).toString()+"px";document.querySelector('textarea').style.width=(innerWidth/2-60).toString()+"px";document.querySelector('hr').style.width=(innerWidth/2-60).toString()+"px";document.querySelector('textarea').style.height=((window.innerHeight-document.querySelector('article p').offsetTop-20-document.querySelector('article p').offsetHeight+3-20*2)/2).toString()+"px";document.querySelector('textarea').addEventListener('focus',function(){this.style.height=(window.innerHeight-document.querySelector('p').offsetTop-20-document.querySelector('article p').offsetHeight+3-20*2).toString()+"px";},false);document.querySelector('textarea').addEventListener('blur',function(){this.style.height=((window.innerHeight-document.querySelector('p').offsetTop-20-document.querySelector('article p').offsetHeight+3-20*2)/2).toString()+"px";},false);window.output_anchor_mouse_location=[];OAML();}
add_styles()
addEventListener('resize',add_styles,false);window.localStorage.setItem('isbn_val_error_nxt',"false");document.querySelector('textarea').addEventListener('keyup',function(e){function moveCaretToEnd(el){if(typeof el.selectionStart=="number"){el.selectionStart=el.selectionEnd=el.value.length;}else if(typeof el.createTextRange!="undefined"){el.focus();var range=el.createTextRange();range.collapse(false);range.select();}}
if(e.keyCode===13){var lst_ln=this.value.split('\\n')[this.value.split('\\n').length-1];if(isbn_check(lst_ln)===false&window.localStorage.getItem('isbn_val_error_nxt')!=="true"){if(lst_ln==""){moveCaretToEnd(this);window.setTimeout(function(){moveCaretToEnd(document.querySelector('textarea'));},1);return;}
x_error(".nonvalid_isbn");document.getElementById('isbn_val_error_close_anch_ff').focus();window.localStorage.setItem('isbn_val_error_nxt',"true");return;}else{window.localStorage.setItem('isbn_val_error_nxt',"false");}
n_handler(this.value.split('\\n'));this.value+="\\n";}
if(window.localStorage.getItem('textarea_previous_value')==null){window.localStorage.setItem('textarea_previous_value',this.value);}
var ol_lns=window.localStorage.getItem('textarea_previous_value').split('\\n');var end_len=ol_lns.length>this.value.split('\\n').length?ol_lns.length:this.value.split('\\n').length;for(i=0;i<end_len;i++){if(this.value.split('\\n')[i]!=ol_lns[i]){sync_hash_to_val();}}
this.value=this.value.replace(/([^\\n\\d]+)/gm,'');},false);document.querySelector('textarea').addEventListener('keypress',function(e){e.preventDefault();var rgx=new RegExp(/\d/);if(String.fromCharCode(e.keyCode).match(rgx)!==null){this.value+=String.fromCharCode(e.keyCode);}},false);addEventListener('DOMContentLoaded',function(){if(typeof window.localStorage.textarea_value!=="undefined"){document.querySelector('textarea').value=window.localStorage.getItem('textarea_value');delete window.localStorage.textarea_value;}},false);document.getElementById('show_howto').addEventListener('click',function(){var v=window.open('https://docs.google.com/viewer?a=v&pid=sites&srcid=ZXVyb3Bhc2tvbGFuLm51fHN2ZW5za2F8Z3g6YTE2NGU3MzE3OGQ0Y2Iz');},false);function create_output_anchor(data){if(document.getElementById("oa_"+data[4])==null){if(typeof document.getElementsByClassName('oa_anchor_elm')[0]!=='undefined'){document.getElementsByClassName('oa_anchor_elm')[0].style.top=data[1]-(document.getElementsByClassName('oa_anchor_elm')[0].offsetHeight/2) + 2 +"px";document.getElementsByClassName('oa_anchor_elm')[0].href=data[5];document.getElementsByClassName('oa_anchor_elm')[0].id="oa_"+data[4];return;}
var an=document.createElement('a');an.innerHTML='&gt;';an.href=data[5];an.id="oa_"+data[4];an.target='_blank';an.className='oa_anchor_elm';document.querySelector('.output_anchor').appendChild(an);an.style.top=data[1]-(an.offsetHeight/2) + 2 +"px";}}
window.addEventListener('load',function(){var b=new window.WebKitBlobBuilder();b.append(document.querySelector('[type="text/outputmousecheck"]').textContent);var url=window.webkitURL.createObjectURL(b.getBlob());window.ww_output_mouse_check=new Worker(url);window.ww_output_mouse_check.addEventListener('message',function(e){if(e.data[0]==true){create_output_anchor(e.data[1]);}else{if(typeof document.getElementsByClassName('oa_anchor_elm')[0]!=='undefined')
for(i=0;i<document.getElementsByClassName('oa_anchor_elm').length;i++)
document.getElementsByClassName('oa_anchor_elm')[i].parentNode.removeChild(document.getElementsByClassName('oa_anchor_elm')[i]);}},false);function oa_eventcaller(e){window.ww_output_mouse_check.postMessage([window.output_anchor_mouse_location,[e.pageX,e.pageY]]);}
document.addEventListener('mousemove',oa_eventcaller,false);document.querySelector('.output').addEventListener('scroll',oa_eventcaller,false);},false);/*]]>*/</script>
            """)
        else:
            self.response.out.write("""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"
   "http://www.w3.org/TR/html4/strict.dtd">
<html>
   <head>
      <title>ISBN</title>
      <link href='https://fonts.googleapis.com/css?family=Lilita+One' rel='stylesheet' type='text/css'>
      <style type='text/css'>
          html
          {
              overflow: hidden;
          }
          body
            {
                background: rgb(69,72,77);
                background: url(data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiA/Pgo8c3ZnIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgdmlld0JveD0iMCAwIDEgMSIgcHJlc2VydmVBc3BlY3RSYXRpbz0ibm9uZSI+CiAgPGxpbmVhckdyYWRpZW50IGlkPSJncmFkLXVjZ2ctZ2VuZXJhdGVkIiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSIgeDE9IjAlIiB5MT0iMCUiIHgyPSIxMDAlIiB5Mj0iMCUiPgogICAgPHN0b3Agb2Zmc2V0PSIwJSIgc3RvcC1jb2xvcj0iIzQ1NDg0ZCIgc3RvcC1vcGFjaXR5PSIxIi8+CiAgICA8c3RvcCBvZmZzZXQ9IjEwMCUiIHN0b3AtY29sb3I9IiMwMDAwMDAiIHN0b3Atb3BhY2l0eT0iMSIvPgogIDwvbGluZWFyR3JhZGllbnQ+CiAgPHJlY3QgeD0iMCIgeT0iMCIgd2lkdGg9IjEiIGhlaWdodD0iMSIgZmlsbD0idXJsKCNncmFkLXVjZ2ctZ2VuZXJhdGVkKSIgLz4KPC9zdmc+);
                background: -moz-linear-gradient(left, rgba(69,72,77,1) 0%, rgba(0,0,0,1) 100%);
                background: -webkit-gradient(linear, left top, right top, color-stop(0%,rgba(69,72,77,1)), color-stop(100%,rgba(0,0,0,1)));
                background: -webkit-linear-gradient(left, rgba(69,72,77,1) 0%,rgba(0,0,0,1) 100%);
                background: -o-linear-gradient(left, rgba(69,72,77,1) 0%,rgba(0,0,0,1) 100%);
                background: -ms-linear-gradient(left, rgba(69,72,77,1) 0%,rgba(0,0,0,1) 100%);
                background: linear-gradient(left, rgba(69,72,77,1) 0%,rgba(0,0,0,1) 100%);
                filter: progid:DXImageTransform.Microsoft.gradient( startColorstr='#45484d', endColorstr='#000000',GradientType=1 );
                
                font-family: 'Lilita One', cursive;
                color: #fbfbfb;
                text-shadow: -1px 0 black, 0 1px black, 1px 0 black, 0 -1px black;
                text-align: center;
            }
            img
            {
                behavior: url(stylesheets/iepngfix.htc);
                border: none;
                outline: none;
                float: left;
                margin: 0;
            }
            a
            {
                float: left;
                border: none;
                outline: none;
                width: 50%;
                margin: 0;
            }
            div
            {
                text-align: center;
                margin: auto;
                display: inline-block;
            }
      </style>
   </head>
   <body>
      <h1>ISBN</h1>
      <div>
            <form method='post' action='/'>
            <input type='hidden' name='t' value='False'>
            <input type='text' name='c'>
            <input type="submit" value="Go!">
        </form>
      </div>
   </body>
</html>
            """)
    def post(self):
        
	# set header
	self.response.headers.add_header("Access-Control-Allow-Origin", "*")
	self.response.headers.add_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
	self.response.headers.add_header("Access-Control-Max-Age", "10000")
	self.response.headers.add_header("Access-Control-Allow-Headers", "Content-Type")
                
        # Get the requests
        
        # isbn doesn't have to be an isbn number, it can be any search query for libris.kb.se
        isbn = self.request.get('c').encode('utf-8')
    
        # if ftype = True then the request was done through ajax
        ftype = self.request.get('t')
        
        # Good thing to remember:
        # self.response.set_status(500)
        
        values = self.MakeQuery(isbn)

        # For Debugging:
        #self.response.out.write(values)
        #return

        if not values:
            params = {'SEARCH_ALL': isbn, 'd':'libris', 'f':'simp', 'spell':'true'}
            url = "http://libris.kb.se/formatQuery.jsp?"
            self.response.out.write("""Your search - %s - did not match any documents. <br><a href="%s" target="_blank">https://libris.kb.se/</a>""" % (isbn, url + self.URLEncode(params), ))
            return
        
        if str(ftype) == 'True':
        
            # Response as json
            self.response.out.write("""{"ISBN": "%s", "Author": "%s", "Title": "%s", "From": "%s", "Publisher": "%s", "'Year'": "%s", "'URL'": "%s"}""" % (values['isbn'], values['author'], values['title'], values['location'], values['publisher'], values['year'], values['url']))
        elif str(ftype) == 'False':
        
            # Response as an HTML page
            self.response.out.write("""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
    <head>
        <title>ISBN</title>
        <link href='https://fonts.googleapis.com/css?family=Lilita+One' rel='stylesheet' type='text/css'>
        <style type='text/css'>
            html
            {
                overflow: hidden;
            }
            body
            {
                background: rgb(69,72,77);
                background: url(data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiA/Pgo8c3ZnIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgdmlld0JveD0iMCAwIDEgMSIgcHJlc2VydmVBc3BlY3RSYXRpbz0ibm9uZSI+CiAgPGxpbmVhckdyYWRpZW50IGlkPSJncmFkLXVjZ2ctZ2VuZXJhdGVkIiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSIgeDE9IjAlIiB5MT0iMCUiIHgyPSIxMDAlIiB5Mj0iMCUiPgogICAgPHN0b3Agb2Zmc2V0PSIwJSIgc3RvcC1jb2xvcj0iIzQ1NDg0ZCIgc3RvcC1vcGFjaXR5PSIxIi8+CiAgICA8c3RvcCBvZmZzZXQ9IjEwMCUiIHN0b3AtY29sb3I9IiMwMDAwMDAiIHN0b3Atb3BhY2l0eT0iMSIvPgogIDwvbGluZWFyR3JhZGllbnQ+CiAgPHJlY3QgeD0iMCIgeT0iMCIgd2lkdGg9IjEiIGhlaWdodD0iMSIgZmlsbD0idXJsKCNncmFkLXVjZ2ctZ2VuZXJhdGVkKSIgLz4KPC9zdmc+);
                background: -moz-linear-gradient(left, rgba(69,72,77,1) 0%%, rgba(0,0,0,1) 100%%);
                background: -webkit-gradient(linear, left top, right top, color-stop(0%%,rgba(69,72,77,1)), color-stop(100%%,rgba(0,0,0,1)));
                background: -webkit-linear-gradient(left, rgba(69,72,77,1) 0%%,rgba(0,0,0,1) 100%%);
                background: -o-linear-gradient(left, rgba(69,72,77,1) 0%%,rgba(0,0,0,1) 100%%);
                background: -ms-linear-gradient(left, rgba(69,72,77,1) 0%%,rgba(0,0,0,1) 100%%);
                background: linear-gradient(left, rgba(69,72,77,1) 0%%,rgba(0,0,0,1) 100%%);
                filter: progid:DXImageTransform.Microsoft.gradient( startColorstr='#45484d', endColorstr='#000000',GradientType=1 );
                font-family: 'Lilita One', cursive; color: #fbfbfb; text-shadow: -1px 0 black, 0 1px black, 1px 0 black, 0 -1px black; text-align: center; 
            } 
            img
            {
                behavior: url(stylesheets/iepngfix.htc);
                border: none;
                outline: none;
                float: left; margin: 0;
            }
            a
            {
                float: left;
                border: none;
                outline: none;
                width: 50%%;
                margin: 0;
            }
            div
            {
                text-align: left;
                margin: auto;
                display: inline-block;
                background-color: white;
                -webkit-border-radius: 12px;
                -moz-border-radius: 12px;
                -o-border-radius: 12px;
                -ms-border-radius: 12px;
                -khtml-border-radius: 12px;
                border-radius: 12px;
                margin: 20px;
                font-family: 'Times New Roman', serif;
                font-size: 12pt;
                color: black;
                text-shadow: none;
                line-height: 200%%;
                margin-left: 40px;
                text-indent: -40px;
                padding: 20px 20px 20px 60px;
            }
        </style>
    </head>
    <body>
        <h1>ISBN</h1>
        <div>%s. %s. %s: %s, %s.</div>
        <br>
        <a href='%s' target='_blank'>Libris.kb.se</a>
        <br>
        <form method='post' action='/'>
            <input type='hidden' name='t' value='False'>
            <input type='text' name='c'>
            <input type='submit' value="Go!">
        </form> 
    </body>
</html>""" % (values['author'], values['title'], values['location'], values['publisher'], values['year'], values['url']))
        elif str(ftype) == 'Gadget':
            # Response as an HTML GADGET page
            self.response.out.write("""
        <style type='text/css'>
            html
            {
                overflow-x: hidden;
                overflow-y: scroll;
		margin: 0;
            }
            body
            {
		margin: 0;
            }
            a
            {
                float: left;
                border: none;
                outline: none;
                width: 50%%;
                margin: 0;
            }
            div
            {
                text-align: left;
                margin: auto;
                display: inline-block;
                background-color: white;
                font-family: 'Times New Roman', serif;
                font-size: 12pt;
                color: black;
                text-shadow: none;
                line-height: 200%%;
                margin-left: 40px;
                text-indent: -40px;
		padding: 5px;
            }
            a, form
            {
            	margin-top: 20px;
		padding-left: 5px;
            }
            form
            {
            	text-align: left;
            }
	    input[type="text"]
	    {
	    	margin: 0;
	    }
        </style>
        <div id='container'>%s. %s. %s: %s, %s.</div>
        <br>
        <a href='%s' target='_blank'>Libris.kb.se</a>
        <br>
        <form method='post' action='https://isbn-f.appspot.com'>
            <input type='hidden' name='t' value='Gadget'>
            <input type='text' name='c'>
            <input type='submit' value="Go!">
        </form>
	<script src='text/javascript'>
		function setWidth() {
			document.getElementById('container').style.width = (window.innerWidth - 40).toString() + "px";
		}
		window.onload = setWidth();
		window.onresize = setWidth();
	</script>
		""" % (values['author'], values['title'], values['location'], values['publisher'], values['year'], values['url']))
        else:
            # Response as an HTML GADGET page
            self.response.out.write("Something went wrong! please go <a href='https://isbn-f.appspot.com'>back</a>.")
                #self.response.out.write("<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\"\"http://www.w3.org/TR/html4/strict.dtd\"><HTML><HEAD><TITLE>ISBN</TITLE><LINK href='http://fonts.googleapis.com/css?family=Lilita+One' rel='stylesheet' type='text/css'><!--[if IE]><STYLE type=\"text/css\">HTML{overflow: hidden;}BODY{background: rgb(69,72,77);background: url(data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiA/Pgo8c3ZnIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgdmlld0JveD0iMCAwIDEgMSIgcHJlc2VydmVBc3BlY3RSYXRpbz0ibm9uZSI+CiAgPGxpbmVhckdyYWRpZW50IGlkPSJncmFkLXVjZ2ctZ2VuZXJhdGVkIiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSIgeDE9IjAlIiB5MT0iMCUiIHgyPSIxMDAlIiB5Mj0iMCUiPgogICAgPHN0b3Agb2Zmc2V0PSIwJSIgc3RvcC1jb2xvcj0iIzQ1NDg0ZCIgc3RvcC1vcGFjaXR5PSIxIi8+CiAgICA8c3RvcCBvZmZzZXQ9IjEwMCUiIHN0b3AtY29sb3I9IiMwMDAwMDAiIHN0b3Atb3BhY2l0eT0iMSIvPgogIDwvbGluZWFyR3JhZGllbnQ+CiAgPHJlY3QgeD0iMCIgeT0iMCIgd2lkdGg9IjEiIGhlaWdodD0iMSIgZmlsbD0idXJsKCNncmFkLXVjZ2ctZ2VuZXJhdGVkKSIgLz4KPC9zdmc+);background: -moz-linear-gradient(left, rgba(69,72,77,1) 0%%, rgba(0,0,0,1) 100%%);background: -webkit-gradient(linear, left top, right top, color-stop(0%%,rgba(69,72,77,1)), color-stop(100%%,rgba(0,0,0,1)));background: -webkit-linear-gradient(left, rgba(69,72,77,1) 0%%,rgba(0,0,0,1) 100%%);background: -o-linear-gradient(left, rgba(69,72,77,1) 0%%,rgba(0,0,0,1) 100%%);background: -ms-linear-gradient(left, rgba(69,72,77,1) 0%%,rgba(0,0,0,1) 100%%);background: linear-gradient(left, rgba(69,72,77,1) 0%%,rgba(0,0,0,1) 100%%);filter: progid:DXImageTransform.Microsoft.gradient( startColorstr='#45484d', endColorstr='#000000',GradientType=1 );font-family: 'Lilita One', cursive;color: #fbfbfb;text-shadow: -1px 0 black, 0 1px black, 1px 0 black, 0 -1px black;text-align: center;}IMG{behavior: url(stylesheets/iepngfix.htc);border: none;outline: none;float: left;margin: 0;}A{float: left;border: none;outline: none;width: 50%%;margin: 0;}DIV{text-align: left;margin: auto;display: inline-block;background-color: white;font-family: 'Times New Roman';font-size: 16px;margin-left: 40px;text-indent: -40px;width: 50%%;-moz-border-radius: 12px;-webkit-border-radius: 12px;border-radius: 12px;padding: 80px;color:black;text-shadow:none;font-weight:normal;line-height:200%%;}</STYLE> </HEAD> <BODY><H1>ISBN<h1><DIV>%s. %s. %s: %s, %s </DIV><BR><A HREF='%s' TARGET='_blank'>Libris.kb.se</A><BR><FORM METHOD='POST' ACTION='http://isbn-f.appspot.com'><INPUT TYPE=HIDDEN NAME='t' VALUE='False'><INPUT TYPE=TEXT NAME='c' MAXLENGTH='13' ONKEYPRESS=\"this.value = this.value.replace(/([^\\d]+)/g,'')\"><INPUT TYPE=SUBMIT></FORM></BODY></HTML>" % (pt['Author'].encode('UTF-8'), pt['Title'].encode('UTF-8'), pt['From'], pt['Publisher'], pt['Year'], pt['URL']))
            

        
def main():
    application = webapp.WSGIApplication([('/', MainHandler)], debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()

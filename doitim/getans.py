import sys
import pycurl
import time
import urlparse
import logging
import signal
import inspect
import urllib

try:
    import html5lib
except ImportError:
    pass


class GetansError(Exception):
    pass

class ResolveError(GetansError):
    pass


class lowgetans(object):
    def __init__(self, url, post = None, ck = "", fail = False, limit = 10000000, ua = "Mozilla/5.0", timeout = 600, bufsize = 120000, vrb = 0, interface = None, headers = None, referer = None, proxy = None, no_encoding = False, opts = {}):
        logging.debug("lowgetans '%s' post: '%s'", url, post)
        _reserved = ';/?:@&=+$|,#' # RFC 3986 (Generic Syntax)
        _unreserved_marks = "-_.!~*'()" # RFC 3986 sec 2.3
        safe_chars = urllib.always_safe + '%' + _reserved + _unreserved_marks

        if isinstance(url, unicode):
            pass
        elif isinstance(url, str):
            pass
        else:
            raise TypeError('getans must receive a unicode or str object, got %s' % type(url).__name__)
        #url = urllib.quote(url, _safe_chars)
            
        scheme, netloc, path, qs, anchor = urlparse.urlsplit(url)
        if isinstance(url, unicode):
            scheme = scheme.encode('utf-8')
            netloc = netloc.encode('idna')
            path = path.encode('utf-8')
            qs = qs.encode('utf-8')
            anchor = anchor.encode('utf-8')
            
        path = urllib.quote(path, safe_chars)
        qs = urllib.quote_plus(qs, safe_chars)
        url = urlparse.urlunsplit((scheme, netloc, path, qs, anchor))

        if referer:
            referer = str(referer)

#        print url
        
        self.__url = url


        self.__loc = False
        self.__nothing = False
        self.__resp = bytearray()
        self.__cut = False
        self.__head = ""
        self.__ctype = None
        self.__code = None
        if isinstance(ck, dict):
            self.__ckarr = ck
        else:
            self.__ckarr = dict(x.strip().split('=', 1) for x in ck.split(';') if x)

        ch = pycurl.Curl()
        ch.setopt(pycurl.URL, url)
        if no_encoding:
            ch.setopt(pycurl.ENCODING, "identity")
        else:
            ch.setopt(pycurl.ENCODING, "")
        ch.setopt(pycurl.USERAGENT, ua)
        ch.setopt(pycurl.FAILONERROR, fail)
        if self.__ckarr:
            ch.setopt(pycurl.COOKIE, "; ".join(k + "=" + v for k,v in self.__ckarr.iteritems()))
        ch.setopt(pycurl.BUFFERSIZE, bufsize)
        ch.setopt(pycurl.SSL_VERIFYPEER, False)
        ch.setopt(pycurl.SSL_VERIFYHOST, False)
        ch.setopt(pycurl.NOSIGNAL, 1)
        ch.setopt(pycurl.VERBOSE, vrb)
        if proxy:
            ch.setopt(pycurl.PROXY, proxy)
        if referer:
            ch.setopt(pycurl.REFERER, referer)
        if headers is None:
            headers = []
        if headers:
            ch.setopt(pycurl.HTTPHEADER, headers)

        if not interface is None:
            ch.setopt(pycurl.INTERFACE, interface)
        
        ch.setopt(pycurl.CONNECTTIMEOUT, timeout)
        ch.setopt(pycurl.TIMEOUT, timeout)
        if post:
            ch.setopt(pycurl.HTTPHEADER, ["Expect: "] + headers)
            if isinstance(post, str):
                ch.setopt(pycurl.POSTFIELDS, post)
            elif isinstance(post, dict):
                ch.setopt(pycurl.HTTPPOST, post.items())
            else:
                raise Exception("OH PPIZD")

            
        self.__tm = time.time()
        self.__cut = False
        
        def wr(buf):
            self.__resp.extend(buf)
            if len(self.__resp) > limit:
                self.__cut = True
                self.__resp = self.__resp[:limit]
                return 0

        def hd(buf):
            self.__head += buf
            buf = buf.rstrip()
            if buf.startswith("Location: "):
                self.__loc = buf.partition("Location: ")[2]
            if buf.lower().startswith("set-cookie: "):
                self.__ckarr.update([buf[len("Set-Cookie: "):].split(';')[0].strip().split('=', 1)]);
                
        ch.setopt(pycurl.WRITEFUNCTION, wr)
        ch.setopt(pycurl.HEADERFUNCTION, hd)

        for k, v in opts.items():
            ch.setopt(k, v)

        mh = pycurl.CurlMulti()
        mh.add_handle(ch)

        while True:
            while True:
                ors = {}
                self.__sigs = set()
                for i in xrange(1, signal.NSIG):
                    si = signal.getsignal(i)
                    if si not in (signal.SIG_IGN, signal.SIG_DFL, None):
                        ors[i] = si
                        
                for i in ors:
                    try:
                        signal.signal(i, lambda sn, fr: self.__sigs.add((sn, fr)))
                    except ValueError:
                        pass

                ret, num = mh.perform()

                for i in ors:
                    try:
                        signal.signal(i, ors[i])
                    except ValueError:
                        pass
                for i, fr in self.__sigs:
                    ors[i](i, inspect.currentframe())
                
                if ret != pycurl.E_CALL_MULTI_PERFORM:
                    break
            if num == 0 : break
            while True:
                sel = mh.select(10)
                if sel != -1 : break

        num_q, ok_list, err_list = mh.info_read()
        mh.remove_handle(ch)
        mh.close()

        if ch in ok_list:
            ps = "OK"
        elif ch in [x for x,y,z in err_list]:
            err, msg = [(y,z) for x,y,z in err_list][0]
            if err == pycurl.E_WRITE_ERROR and self.__cut:
                ps = "OK-CUT"
            elif err == pycurl.E_GOT_NOTHING:
                self.__nothing = True
                ps = "OK-NOTHING"
            elif err == pycurl.E_COULDNT_RESOLVE_HOST:
                ch.close()
                raise ResolveError(msg)
            else:
                ch.close()
                raise GetansError(msg)
        else:
            raise Exception("pizdec")
        
        self.__ctype = ch.getinfo(pycurl.CONTENT_TYPE)
        self.__code = ch.getinfo(pycurl.HTTP_CODE)
        ch.close()
        logging.debug("lowgetans %s:%d [%d]", ps, self.__code, len(self.__resp))

    def body(self):
        return self.__resp

    def encoding(self):
        return html5lib.inputstream.ContentAttrParser(html5lib.inputstream.EncodingBytes(self.ctype())).parse()

    def parse_html(self):
        if self.ctype() and (self.ctype().startswith("text/html") or self.ctype().startswith("application/xhtml+xml")):
            return html5lib.parse(self.body(), "lxml", self.encoding(), False)
        else:
            return None

    def code(self):
        return self.__code

    def head(self) :
        return self.__head
    
    def cookies(self) :
        return self.__ckarr

    def url(self):
        return self.__url
    
    def ctype(self) :
        return self.__ctype

    def redurl(self):
        if self.__loc is False:
            return False
        return urlparse.urljoin(self.__url, self.__loc)

    def nothing(self):
        return self.__nothing

    def full(self):
        return self.__head + self.__resp

    def __str__(self):
        return str(self.__resp)






class getans(lowgetans):
    
    @staticmethod
    def file(fn):
        open(fn).close()
        return (pycurl.FORM_FILE, fn)

    proxy = None
    interface = None
    
#    __follows = 0
    def __init__(self, url, post = None, ck = "", fail = False, limit = 12000000, ua = "Mozilla/5.0", timeout = 600, tries = 10, anotry = True, follow = False, nothings = 3, bufsize = 120000, vrb = 0, interface = None, headers = None, referer = None, proxy = None, no_encoding = False, opts={}):
        if proxy is None:
            proxy = self.proxy
        if interface is None:
            interface = self.interface
        logging.info("getans '%s'", url)
        reserr = 0
        fe = ""
        errs = 0
        noths = 0
        while errs < tries:
            try:
                lowgetans.__init__(self, url, post, ck, fail, limit, ua, timeout, bufsize, vrb, interface, headers, referer, proxy, no_encoding, opts)
                errs = 0
                reserr = 0
                if self.nothing():
                    noths += 1
                if nothings and self.nothing():
                    nothings -= 1
                elif follow and self.redurl():
                    follow -= 1
                    logging.info(u"getans redirect '%s' -> '%s'", url, self.redurl())
                    url = self.redurl()
#                    self.__follows += 1
                    post = None
                else:
                    return
            except ResolveError, e:
                reserr += 1
                errs += 1
                logging.info("getans " + e.args[0])
                if errs == 1:
                    fe = e
                if anotry and reserr % 2 == 0:
                    url = anourl(url)
            except GetansError, e:
                logging.info("getans " + e.args[0])
                errs += 1
                if errs == 1:
                    fe = e
            except SyntaxError:
                raise GetansError(url + "redirects to bad url " + self.redurl())
        raise fe

def anohost(host):
    if host.startswith("www."):
        return host[4:]
    else:
        return "www." + host

def anoscheme(scheme):
    if scheme == 'http':
        return 'https'
    elif scheme == 'https':
        return 'http'
    else:
        return scheme

def canohost(host):
    if host.startswith('www.'):
        return canohost(host[4:])
    elif host.startswith('ww.'):
        return canohost(host[3:])
    else:
        return host

def unihosts(a):
    ct = set()
    for x in a:
        if canohost(x) not in ct:
            ct.add(canohost(x))
            yield x

def uniurls(a):
    ct = set()
    for x in a:
        if x not in ct:
            ct |= sameurls(x)
            yield x


def anourl(url, host = True, scheme = False):
    a = urlparse.urlparse(url)
    b = a.netloc.split('@')
    a = list(a)
    if scheme:
        a[0] = anoscheme(a[0])
    if  '[' == b[-1][0] and ']' in b[-1]:
        return urlparse.urlunparse(a)
    elif ':' in b[-1]:
        b1, t, b2 = b[-1].partition(':')
        if host:
            b[-1] = anohost(b1) + ':' + b2
        a[1] = '@'.join(b)
        return urlparse.urlunparse(a)
    elif b[-1] == '':
        return urlparse.urlunparse(a)
    else:
        if host:
            b[-1] = anohost(b[-1])
        a[1] = '@'.join(b)
        return urlparse.urlunparse(a)

def sameurls(url):
    return set([url, anourl(url, True, False), anourl(url, True, True), anourl(url, False, True)])

def urlcompare(a, b):
    return a in sameurls(b)


if __name__ == '__main__':
    print getans(sys.argv[1])




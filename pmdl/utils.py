import os
import time
import urlparse
import mimetypes

from lxml import html
import requests

from errors import *
from common import *

def get_publisher_links(pubmed_id, retry=3):
    '''Get publisher links from PubMed
    '''

    pubmed_url = 'http://www.ncbi.nlm.nih.gov/pubmed/{pmid}'.format(pmid=pubmed_id)

    for i in xrange(retry):
        response = requests.get(pubmed_url, timeout=DEFAULT_TIMEOUT)

        if str(response.status_code) != '200':
            print '[WARN] Status code: {code}'.format(code=response.status_code)
        else:
            body = html.fromstring(response.content)
            links = body.xpath('//span[text()="Full text links"]/../../../../a/@href')

            if links:
                print '[INFO] Publisher links:', links
                return links

        print '[WARN] Wait a while and retry getting publisher links...'
        requests.get('https://www.google.com/', timeout=DEFAULT_TIMEOUT)
        time.sleep(60)

    raise PubmedPdfDownloaderError('Publisher links not found')

def absolute_url(response, relative_url, base='/'):
    base = urlparse.urljoin(response.url, base)
    return os.path.join(base, relative_url.lstrip('/'))

def download_file(url, dst, overwrite=False):
    '''Save response as file to dst path
    '''

    print '[INFO] Download from:', url

    if not overwrite and os.path.exists(dst):
        print '[INFO] File already exists. Skip donwloading', dst
        return

    response = requests.get(url, timeout=DEFAULT_TIMEOUT)


    # FIXME:
    if 'html' in response.headers.get('Content-Type'):
        raise PubmedPdfDownloaderError('Failed. Maybe not open access article')

    # Guess extension and add to file name if not exists
    ext_by_mime = guess_extensions(response)
    if ext_by_mime:
        _, ext = os.path.splitext(dst)

        if not ext.lower() in ext_by_mime:
            dst = dst + ext_by_mime[0]
    else:
        print '[WARN] ext_by_mime not found', response.headers.get('Content-Type')

    if not overwrite and os.path.exists(dst):
        print '[INFO] File already exists. Skip donwloading', dst
        return

    with open(dst, 'wb') as fout:
        fout.write(response.content)
    print '[INFO] Downloaded to:', dst

def guess_extensions(response):
    '''Guess extension by Content-Type
    '''

    mime = response.headers.get('Content-Type')

    # ugly hardcoding but to use '.ppt' instead of '.pwz' etc., define MIME Types for MS files
    mime2ext = {
        # cf. Office 2007 File Format MIME Types for HTTP Content Streaming
        # http://blogs.msdn.com/b/vsofficedeveloper/archive/2008/05/08/office-2007-open-xml-mime-types.aspx
        'application/msword': ['.doc', '.dot'],
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
        'application/vnd.openxmlformats-officedocument.wordprocessingml.template': ['.dotx'],
        'application/vnd.ms-word.document.macroEnabled.12': ['.docm'],
        'application/vnd.ms-word.template.macroEnabled.12': ['.dotm'],
        'application/vnd.ms-excel': ['.xls', '.xlt', '.xla'],
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
        'application/vnd.openxmlformats-officedocument.spreadsheetml.template': ['.xltx'],
        'application/vnd.ms-excel.sheet.macroEnabled.12': ['.xlsm'],
        'application/vnd.ms-excel.template.macroEnabled.12': ['.xltm'],
        'application/vnd.ms-excel.addin.macroEnabled.12': ['.xlam'],
        'application/vnd.ms-excel.sheet.binary.macroEnabled.12': ['.xlsb'],
        'application/vnd.ms-powerpoint': ['.ppt', '.pot', '.pps', '.ppa'],
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
        'application/vnd.openxmlformats-officedocument.presentationml.template': ['.potx'],
        'application/vnd.openxmlformats-officedocument.presentationml.slideshow': ['.ppsx'],
        'application/vnd.ms-powerpoint.addin.macroEnabled.12': ['.ppam'],
        'application/vnd.ms-powerpoint.presentation.macroEnabled.12': ['.pptm', '.potm'],
        'application/vnd.ms-powerpoint.slideshow.macroEnabled.12': ['.ppsm'],

        # '.jpg' instead of '.jpe' etc.
        'image/jpeg': ['.jpg', '.jpe', '.jpeg', '.jfif'],
        'text/plain': ['.txt', '.ksh', '.pl', '.bat', '.h', '.c', '.asc', '.text', '.pm', '.el', '.cc', '.hh', '.cxx', '.hxx', '.f90', '.conf', '.log'],
    }

    ext = mime2ext.get(mime) or mimetypes.guess_all_extensions(mime)

    return ext

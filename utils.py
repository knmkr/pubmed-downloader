import os
import urlparse
import mimetypes

from lxml import html
import requests

from errors import *


def get_publisher_links(pubmed_id):
    '''Get publisher links from PubMed
    '''

    pubmed_url = 'http://www.ncbi.nlm.nih.gov/pubmed/{pmid}'.format(pmid=pubmed_id)
    response = requests.get(pubmed_url)
    body = html.fromstring(response.content)
    links = body.xpath('//span[text()="Full text links"]/../../../../a/@href')

    if not links:
        raise PubmedPdfDownloaderError('Publisher links not found')

    print '[INFO] Publisher links:', links
    return links

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

    response = requests.get(url)

    # FIXME:
    if 'html' in response.headers.get('Content-Type'):
        raise PubmedPdfDownloaderError('Failed. Maybe not open access article')

    # FIXME:
    ext_by_mime = guess_extention(response)
    if ext_by_mime:
        _, ext = os.path.splitext(dst)
        if ext.lower() != ext_by_mime:
            dst = dst + ext_by_mime
    else:
        print '[DEBUG] ext_by_mime not found', response.headers.get('Content-Type')

    if not overwrite and os.path.exists(dst):
        print '[INFO] File already exists. Skip donwloading', dst
        return

    with open(dst, 'wb') as fout:
        fout.write(response.content)
    print '[INFO] Downloaded to:', dst

def guess_extention(response):
    '''TODO:

    - Office 2007 File Format MIME Types for HTTP Content Streaming
    http://blogs.msdn.com/b/vsofficedeveloper/archive/2008/05/08/office-2007-open-xml-mime-types.aspx
    '''

    mime = response.headers.get('Content-Type')

    ms_mime2ext = {
        'application/msword': '.doc',
        # 'application/msword': '.dot',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.template': '.dotx',
        'application/vnd.ms-word.document.macroEnabled.12': '.docm',
        'application/vnd.ms-word.template.macroEnabled.12': '.dotm',
        'application/vnd.ms-excel': '.xls',
        # 'application/vnd.ms-excel': '.xlt',
        # 'application/vnd.ms-excel': '.xla',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.template': '.xltx',
        'application/vnd.ms-excel.sheet.macroEnabled.12': '.xlsm',
        'application/vnd.ms-excel.template.macroEnabled.12': '.xltm',
        'application/vnd.ms-excel.addin.macroEnabled.12': '.xlam',
        'application/vnd.ms-excel.sheet.binary.macroEnabled.12': '.xlsb',
        'application/vnd.ms-powerpoint': '.ppt',
        # 'application/vnd.ms-powerpoint': '.pot',
        # 'application/vnd.ms-powerpoint': '.pps',
        # 'application/vnd.ms-powerpoint': '.ppa',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
        'application/vnd.openxmlformats-officedocument.presentationml.template': '.potx',
        'application/vnd.openxmlformats-officedocument.presentationml.slideshow': '.ppsx',
        'application/vnd.ms-powerpoint.addin.macroEnabled.12': '.ppam',
        'application/vnd.ms-powerpoint.presentation.macroEnabled.12': '.pptm',
        # 'application/vnd.ms-powerpoint.presentation.macroEnabled.12': '.potm',
        'application/vnd.ms-powerpoint.slideshow.macroEnabled.12': '.ppsm'
    }

    ext = ms_mime2ext.get(mime, '')
    if ext:
        return ext

    ext = mimetypes.guess_extension(mime) or ''
    return ext

import os
import re
import urlparse
import argparse

from lxml import html
import requests

from errors import *
from utils import *
from common import *

def nat_genet_downloader(pubmed_id, publisher_link, args):
    '''Download from Nat Genet

    E.g.
    - open access: 26752266
    - non-open access: 25774636
    '''

    print '[INFO] PMID {pmid} Try to download from Nat Genet'.format(pmid=pubmed_id)

    response = requests.get(publisher_link, timeout=DEFAULT_TIMEOUT)

    if str(response.status_code) == '401':
        raise PubmedPdfDownloaderError('Failed. Maybe not open access article')
    elif str(response.status_code) != '200':
        raise PubmedPdfDownloaderError('Failed. Status code: {code}'.format(code=response.status_code))

    url = response.url

    if not '/journal' in url:
        print '[INFO] Download by publisher link in PubMed faild. Try to download by doi search'
        doi_a, doi_b = re.findall(r'.*dx.doi.org/([\d\.]+)/(ng[\d\.]+)', publisher_link)[0]
        response = requests.get('http://www.nature.com/search?order=relevance&q={doi_a}%2F{doi_b}'.format(doi_a=doi_a, doi_b=doi_b), timeout=DEFAULT_TIMEOUT)
        body = html.fromstring(response.content)
        url_founds = [url for url in body.xpath('//a/@href') if '/journal' in url]
        if len(url_founds) == 1:
            url = url_founds[0]
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
        else:
            raise PubmedPdfDownloaderError('Failed.'.format(response.url))

    # Download full text pdf
    pdf_url = os.path.join(os.path.dirname(os.path.dirname(url)), 'pdf', os.path.basename(url).replace('.html', '') + '.pdf')
    download_file(pdf_url, os.path.join(args.dst_dir, 'PMID{pmid}.pdf'.format(pmid=pubmed_id)), overwrite=args.overwrite)

    # Download supplemental materials
    body = html.fromstring(response.content)
    supplemental_file_urls = [url for url in body.xpath('//h1[text()="Supplementary information"]/following-sibling::*//a/@href') if not url.startswith('#')]

    i = 1
    for url in supplemental_file_urls:
        url = absolute_url(response, url)

        try:
            _, extension = os.path.splitext(url)
            download_file(url, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extension}'.format(pmid=pubmed_id, i=i, extension=extension)), overwrite=args.overwrite)
            i += 1
        except PubmedPdfDownloaderError as e:
            print '[INFO] External link found. Maybe Supplemental figures:', url
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            body = html.fromstring(response.content)
            ext_urls = body.xpath('//figure//img/@src')

            if len(ext_urls) == 1:
                ext_url = absolute_url(response, ext_urls[0])
                _, extension = os.path.splitext(ext_url)
                download_file(ext_url, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extension}'.format(pmid=pubmed_id, i=i, extension=extension)), overwrite=args.overwrite)
                i += 1
            else:
                print '[WARN] Faild. Maybe not supplemental files:', url

def plos_downloader(pubmed_id, publisher_link, args):
    '''Download from PLoS Genet/One

    E.g.
    - open access PLoS Genet: 17447842 17658951
    - open access PLoS One: 17684544
    '''

    print '[INFO] PMID {pmid} Try to download from PLoS Genet/One'.format(pmid=pubmed_id)

    if 'journal.pgen' in publisher_link:
        base = '/plosgenetics'
    elif 'journal.pone' in publisher_link:
        base = '/plosone'
    else:
        raise PubmedPdfDownloaderError('Unexpected url for plos_downloader: ' + publisher_link)

    response = requests.get(publisher_link, timeout=DEFAULT_TIMEOUT)

    if str(response.status_code).startswith('4'):
        raise PubmedPdfDownloaderError('Failed. Status code: {code}'.format(code=response.status_code))

    # Get link to supplemental materials
    body = html.fromstring(response.content)
    supplemental_file_urls = [absolute_url(response, url, base=base) for url in body.xpath('//h2[text()="Supporting Information"]/following-sibling::*//a/@href') if not url.startswith('#')]

    print '[DEBUG] supplemental_file_urls', supplemental_file_urls

    # Download full text pdf
    pdf_urls = body.xpath('//a[text()="Download PDF"]/@href')

    if not pdf_urls:
        raise PubmedPdfDownloaderError('Full text pdf not found')

    pdf_url = absolute_url(response, pdf_urls[0])
    download_file(pdf_url, os.path.join(args.dst_dir, 'PMID{pmid}.pdf'.format(pmid=pubmed_id)), overwrite=args.overwrite)

    # Download supplemental materials
    if not supplemental_file_urls:
        print '[WARN] Supplemental materials not found'
        return

    for i, supplemental_file_url in enumerate(supplemental_file_urls):
        _, extension = os.path.splitext(supplemental_file_url)
        download_file(supplemental_file_url, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extension}'.format(pmid=pubmed_id, i=i+1, extension=extension)), overwrite=args.overwrite)
    return

def oxford_journals_downloader(pubmed_id, publisher_link, args):
    '''Downlaod from OXFORD JOURNALS

    E.g.
    - open access: 23612905 25628336
    - non-open access: 25429064
    '''

    print '[INFO] PMID {pmid} Try to download from OXFORD JOURNALS'.format(pmid=pubmed_id)

    # FIXME *.oxfordjournals.org?
    url = 'http://hmg.oxfordjournals.org/cgi/pmidlookup?pmid={pmid}'.format(pmid=pubmed_id)
    response = requests.get(url, timeout=DEFAULT_TIMEOUT)

    if str(response.status_code).startswith('4'):
        raise PubmedPdfDownloaderError('Failed. Status code:{code}'.format(code=response.status_code))

    # Get link to supplemental materials
    body = html.fromstring(response.content)
    supplemental_relative_urls = body.xpath('//a[text()="Supplementary Data"]/@href')

    # Download full text pdf
    pdf_url = response.url.strip('/') + '.full.pdf'
    download_file(pdf_url, os.path.join(args.dst_dir, 'PMID{pmid}.pdf'.format(pmid=pubmed_id)), overwrite=args.overwrite)

    # Download supplemental materials
    if not supplemental_relative_urls:
        print '[WARN] Supplemental materials not found'
        return

    supplemental_url = absolute_url(response, supplemental_relative_urls[0])
    response = requests.get(supplemental_url, timeout=DEFAULT_TIMEOUT)
    body = html.fromstring(response.content)
    supplemental_file_urls = [absolute_url(response, href) for href in body.xpath('//h2[text()="Supplementary Data"]/following-sibling::ul/li/a/@href')]

    if not supplemental_file_urls:
        raise PubmedPdfDownloaderError('Link to supplemental materials exists, but files not found')

    for i, supplemental_file_url in enumerate(supplemental_file_urls):
        _, extension = os.path.splitext(supplemental_file_url)
        download_file(supplemental_file_url, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extension}'.format(pmid=pubmed_id, i=i+1, extension=extension)), overwrite=args.overwrite)

    return

def pmc_downloader(pubmed_id, publisher_link, args):
    '''Downlaod from PMC

    E.g.
    - 21572416 25187374
    '''

    print '[INFO] PMID {pmid} Try to download from PMC'.format(pmid=pubmed_id)

    pdf_url = 'http://www.ncbi.nlm.nih.gov/pmc/articles/pmid/{pmid}/pdf'.format(pmid=pubmed_id)
    download_file(pdf_url, os.path.join(args.dst_dir, 'PMID{pmid}.pdf'.format(pmid=pubmed_id)), overwrite=args.overwrite)

    url = 'http://www.ncbi.nlm.nih.gov/pmc/articles/pmid/{pmid}'.format(pmid=pubmed_id)
    response = requests.get(url, timeout=DEFAULT_TIMEOUT)
    body = html.fromstring(response.content)
    # FIXME
    supplemental_file_urls = body.xpath('//h2[text()="Supplementary Material" or text()="SUPPLEMENTARY MATERIAL" or text()="Supplemental Data" or text()="SUPPLEMENTAL DATA"]/parent::node()/descendant::*/a/@href')

    # TBD: use PMC API? (http://europepmc.org/RestfulWebService#suppFiles)

    i = 1
    for url in supplemental_file_urls:
        url = absolute_url(response, url)

        try:
            _, extension = os.path.splitext(url)
            download_file(url, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extension}'.format(pmid=pubmed_id, i=i, extension=extension)), overwrite=args.overwrite)
            i += 1
        except PubmedPdfDownloaderError as e:
            # External link to supplementary materials
            print '[INFO] External link found:', url
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            body = html.fromstring(response.content)
            ext_urls = [os.path.join(os.path.dirname(response.url), link) for link in body.xpath('//a/@href')]

            for ext_url in ext_urls:
                _, extension = os.path.splitext(ext_url)
                download_file(ext_url, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extension}'.format(pmid=pubmed_id, i=i, extension=extension)), overwrite=args.overwrite)
                i += 1

    return


if __name__ == '__main__':
    main()

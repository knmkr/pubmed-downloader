#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import urlparse
import argparse

from lxml import html
import requests

def main():
    parser = argparse.ArgumentParser(description='Downlaod open access full text pdf and supplemental materials of each PubMed IDs.')
    parser.add_argument('--pubmed-ids', nargs='+', required=True, help='PubMed IDs')
    parser.add_argument('--dst-dir', default='.', help='destination directory')
    args = parser.parse_args()

    downloaders = {
        'oxfordjournals.org': oxford_journals_downloader,
        # 'www.ncbi.nlm.nih.gov/pmc': pmc_downloader,
    }

    for pubmed_id in args.pubmed_ids:
        print '[INFO] Pubmed ID:', pubmed_id

        # Get publisher information
        publisher_links = get_publisher_links(pubmed_id)

        if not publisher_links:
            print '[INFO] Publisher links not found'
            continue

        # Select downloader by publisher information
        downloader = None
        for publisher_link in publisher_links:
            for pattern, _downloader in downloaders.items():
                if pattern in publisher_link:
                    downloader = _downloader

        if not downloader:
            print '[INFO] Not supported publisher'
            continue

        # Download full text and supplemental materials
        is_downloaded = downloader(pubmed_id, args)

        if not is_downloaded:
            print '[INFO] Download failed'
            continue

def oxford_journals_downloader(pubmed_id, args):
    '''Downlaod from OXFORD JOURNALS

    E.g.
    - open access: 23612905 25628336
    - non-open access: 25429064
    '''

    print '[INFO] Try to download from OXFORD JOURNALS'

    # FIXME *.oxfordjournals.org?
    url = 'http://hmg.oxfordjournals.org/cgi/pmidlookup?pmid={pmid}'.format(pmid=pubmed_id)
    response = requests.get(url)

    if str(response.status_code).startswith('4'):
        print '[ERROR] Failed. Status code:', response.status_code
        return False

    # Get link to supplemental materials
    body = html.fromstring(response.content)
    supplemental_relative_urls = body.xpath('//a[text()="Supplementary Data"]/@href')

    # Download full text pdf
    pdf_url = response.url.strip('/') + '.full.pdf'
    is_downloaded = download_file(pdf_url, os.path.join(args.dst_dir, 'PMID{pmid}.pdf'.format(pmid=pubmed_id)))

    if not is_downloaded:
        return False

    # Download supplemental materials
    if not supplemental_relative_urls:
        print '[WARN] Supplemental materials not found'
        return True

    supplemental_url = absolute_url(response, supplemental_relative_urls[0])
    response = requests.get(supplemental_url)
    body = html.fromstring(response.content)
    supplemental_file_urls = [absolute_url(response, href) for href in body.xpath('//h2[text()="Supplementary Data"]/following-sibling::ul/li/a/@href')]

    if not supplemental_file_urls:
        print '[WARN] Link to supplemental materials exists, but files not found'
        return False
    else:
        for i, supplemental_file_url in enumerate(supplemental_file_urls):
            _, extention = os.path.splitext(supplemental_file_url)
            download_file(supplemental_file_url, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extention}'.format(pmid=pubmed_id, i=i+1, extention=extention)))

            if not is_downloaded:
                return False

        return True

def pmc_downloader(pubmed_id, args):
    '''Downlaod from PMC
    '''

    print '[INFO] Try to download from PMC'

    pdf_url = 'http://www.ncbi.nlm.nih.gov/pmc/articles/pmid/{pmid}/pdf'.format(pmid=pubmed_id)
    print '[INFO] Download from:', pdf_url

    response = requests.get(pdf_url)

    if str(response.status_code).startswith('4'):
        print '[INFO] Failed. Status code:', response.status_code
        return False

    download(response, os.path.join(args.dst_dir, 'PMID{pmid}.pdf'.format(pmid=pubmed_id)))

    url = 'http://www.ncbi.nlm.nih.gov/pmc/articles/pmid/{pmid}'.format(pmid=pubmed_id)
    print '[INFO] Try to download supplementary materials from:', url

    response = requests.get(url)
    body = html.fromstring(response.content)
    # FIXME
    supplementary_material_urls = body.xpath('//h2[text()="Supplementary Material" or text()="SUPPLEMENTARY MATERIAL" or text()="Supplemental Data" or text()="SUPPLEMENTAL DATA"]/parent::node()/descendant::*/a/@href')

    # TBD: use PMC API? (http://europepmc.org/RestfulWebService#suppFiles)

    i = 1
    for url in supplementary_material_urls:
        url = absolute_url(response, url)
        response = requests.get(url)

        # Direct link to a supplementary material
        if not 'html' in response.headers.get('Content-Type'):
            _, extention = os.path.splitext(url)
            download(response, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extention}'.format(pmid=pubmed_id, i=i, extention=extention)))
            i += 1
            continue

        # External link to supplementary materials
        print '[INFO] External link found:', url
        body = html.fromstring(response.content)
        # FIXME
        external_urls = [link for link in body.xpath('//a/@href') if link.endswith(('.pdf',
                                                                                    '.doc',
                                                                                    '.docx',
                                                                                    '.xls',
                                                                                    '.xlsx',
                                                                                    '.ppt',
                                                                                    '.pptx',
                                                                                    '.txt',
                                                                                    '.csv',
                                                                                    '.jpg',
                                                                                    '.jpeg',
                                                                                    '.png',
                                                                                    '.tif',
                                                                                    '.tiff',))]

        for ext_url in external_urls:
            ext_url = absolute_url(response, ext_url)
            _, extention = os.path.splitext(ext_url)
            download(os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extention}'.format(pmid=pubmed_id, i=i, extention=extention)))
            i += 1

    return True

def get_publisher_links(pubmed_id):
    '''Get publisher links from PubMed
    '''

    pubmed_url = 'http://www.ncbi.nlm.nih.gov/pubmed/{pmid}'.format(pmid=pubmed_id)
    response = requests.get(pubmed_url)
    body = html.fromstring(response.content)
    links = body.xpath('//span[text()="Full text links"]/../../../../a/@href')
    print '[INFO] Publisher links:', links

    return links

def absolute_url(response, relative_url):
    base = urlparse.urljoin(response.url, '/')
    return os.path.join(base, relative_url.lstrip('/'))

def download_file(url, dst):
    '''Save response as file to dst path
    '''

    print '[INFO] Download from:', url
    response = requests.get(url)

    # FIXME:
    if 'html' in response.headers.get('Content-Type'):
        print '[ERROR] Failed. Maybe not open access article'
        return False

    with open(dst, 'wb') as fout:
        fout.write(response.content)
    print '[INFO] Downloaded to:', dst

    return True

if __name__ == '__main__':
    main()

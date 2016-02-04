#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import urlparse
import argparse

from lxml import html
import requests

from errors import *
from utils import *


# TODO: install and execute as pypi package. cf. local install of py-vcf-parser
def main():
    parser = argparse.ArgumentParser(description='Downlaod open access full text pdf and supplemental materials of each PubMed IDs.')
    parser.add_argument('--pubmed-ids', nargs='+', required=True, help='PubMed IDs')
    parser.add_argument('--dst-dir', default='.', help='Destination directory')
    parser.add_argument('-w', '--overwrite', action='store_true', help='Allow overwriting if downloaded files already exist. Default: False')
    args = parser.parse_args()

    downloaders = {
        'oxfordjournals.org': oxford_journals_downloader,  # Hum Mol Genet
        'plos.org': plos_downloader,                       # PLoS Genet, PLoS One
        # '': nat_genet_downloader,                        # TODO: Nat Genet
        # 'www.ncbi.nlm.nih.gov/pmc': pmc_downloader,      # TODO: PMC
    }

    for pubmed_id in args.pubmed_ids:
        print '[INFO] Pubmed ID:', pubmed_id

        try:
            # Get publisher information
            publisher_links = get_publisher_links(pubmed_id)

            # Select downloader by publisher information
            downloader = None
            for link in publisher_links:
                for pattern, _downloader in downloaders.items():
                    if pattern in link:
                        publisher_link, downloader = link, _downloader
                        break

            if not downloader:
                raise PubmedPdfDownloaderError('Not supported publisher')

            # Download full text and supplemental materials
            downloader(pubmed_id, publisher_link, args)

        except PubmedPdfDownloaderError as e:
            print '[ERROR]', e

def plos_downloader(pubmed_id, publisher_link, args):
    '''Download from PLOS Genetics

    E.g.
    - open access PLOS Genet: 17447842 17658951
    - open access PLOS One: 17684544
    '''

    print '[INFO] Try to download from PLOS Genetics/One'

    if 'journal.pgen' in publisher_link:
        base = '/plosgenetics'
    elif 'journal.pone' in publisher_link:
        base = '/plosone'
    else:
        raise PubmedPdfDownloaderError('Unexpected url for plos_downloader: ' + publisher_link)

    response = requests.get(publisher_link)

    if str(response.status_code).startswith('4'):
        raise PubmedPdfDownloaderError('Failed. Status code: {}'.format(response.status_code))

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
        _, extention = os.path.splitext(supplemental_file_url)
        download_file(supplemental_file_url, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extention}'.format(pmid=pubmed_id, i=i+1, extention=extention)), overwrite=args.overwrite)
    return


def oxford_journals_downloader(pubmed_id, publisher_link, args):
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
        raise PubmedPdfDownloaderError('Failed. Status code:{}'.format(response.status_code))

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
    response = requests.get(supplemental_url)
    body = html.fromstring(response.content)
    supplemental_file_urls = [absolute_url(response, href) for href in body.xpath('//h2[text()="Supplementary Data"]/following-sibling::ul/li/a/@href')]

    if not supplemental_file_urls:
        raise PubmedPdfDownloaderError('Link to supplemental materials exists, but files not found')

    for i, supplemental_file_url in enumerate(supplemental_file_urls):
        _, extention = os.path.splitext(supplemental_file_url)
        download_file(supplemental_file_url, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extention}'.format(pmid=pubmed_id, i=i+1, extention=extention)), overwrite=args.overwrite)

    return


def pmc_downloader(pubmed_id, publisher_link, args):
    '''Downlaod from PMC
    '''
    #
    raise PubmedPdfDownloaderError('Depricated downloder: pmc_downloader')

    print '[INFO] Try to download from PMC'

    pdf_url = 'http://www.ncbi.nlm.nih.gov/pmc/articles/pmid/{pmid}/pdf'.format(pmid=pubmed_id)
    print '[INFO] Download from:', pdf_url

    response = requests.get(pdf_url)

    if str(response.status_code).startswith('4'):
        print '[INFO] Failed. Status code:', response.status_code
        return False

    download(response, os.path.join(args.dst_dir, 'PMID{pmid}.pdf'.format(pmid=pubmed_id)), overwrite=args.overwrite)

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
            download(response, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extention}'.format(pmid=pubmed_id, i=i, extention=extention)), overwrite=args.overwrite)
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
            download(os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extention}'.format(pmid=pubmed_id, i=i, extention=extention)), overwrite=args.overwrite)
            i += 1

    return True


if __name__ == '__main__':
    main()

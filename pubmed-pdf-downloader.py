#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import requests
import urlparse
import argparse
from lxml import html


def _main():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--pubmed-id', help='')
    parser.add_argument('--dst-dir', default='.', help='')
    args = parser.parse_args()

    print '[INFO] PMID:', args.pubmed_id

    # TODO: catch exception

    url = 'http://www.ncbi.nlm.nih.gov/pmc/articles/pmid/{pmid}/pdf'.format(pmid=args.pubmed_id)

    print '[INFO] Try to download full text pdf from:', url
    response = requests.get(url)
    outfile = 'PMID{pmid}.pdf'.format(pmid=args.pubmed_id)
    dst = os.path.join(args.dst_dir, outfile)
    with open(dst, 'wb') as fout:
        fout.write(response.content)
    print '[INFO] Downloaded:', dst

    url = 'http://www.ncbi.nlm.nih.gov/pmc/articles/pmid/{pmid}'.format(pmid=args.pubmed_id)

    print '[INFO] Try to download supplementary materials from:', url

    response = requests.get(url)
    body = html.fromstring(response.content)
    supplementary_material_urls = body.xpath('//h2[text()="Supplementary Material" or text()="SUPPLEMENTARY MATERIAL"]/parent::node()/descendant::*/a/@href')

    i = 1
    for url in supplementary_material_urls:
        if url.startswith('/'):
            url = 'http://www.ncbi.nlm.nih.gov' + url

        response = requests.get(url)

        if not 'html' in response.headers.get('Content-Type'):
            _, extention = os.path.splitext(url)
            outfile = 'PMID{pmid}_S{i}{extention}'.format(pmid=args.pubmed_id, i=i, extention=extention)
            dst = os.path.join(args.dst_dir, outfile)
            with open(dst, 'wb') as fout:
                fout.write(response.content)
            i += 1
            print '[INFO] Downloaded:', dst
            continue

        print '[INFO] External link found:', url

        body = html.fromstring(response.content)
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
                                                                                    '.tiff',))]  # FIXME

        for ext_url in external_urls:
            if ext_url.startswith('/'):
                ext_url = urlparse.urljoin(response.url, '/') + ext_url

            _, extention = os.path.splitext(ext_url)
            outfile = 'PMID{pmid}_S{i}{extention}'.format(pmid=args.pubmed_id, i=i, extention=extention)
            dst = os.path.join(args.dst_dir, outfile)
            with open(dst, 'wb') as fout:
                fout.write(response.content)
            i += 1
            print '[INFO] Downloaded:', dst
            continue


if __name__ == '__main__':
    _main()

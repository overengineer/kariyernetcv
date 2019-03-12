from utils import *
from lxml import html, etree
import os,sys
import requests
import json

def text(el, query, sep=' ', select=''):
	s = el.xpath(query + select + '/text()')
	if type(s) is list:
		s = sep.join(s)
	return s

by_class = '//*[contains(@class,"%s")]'

assert len(sys.argv)==2, "usage: python3 %s [YOUR KARIYER.NET PUBLIC CV URL]" % __file__

response = requests.get(sys.argv[1])
page = html.fromstring(response.content)
page = page.xpath('//body')[0]

cv = {
	'name'    : text(page,by_class % 'candidate-name'),
	'job'     : text(page,by_class % 'candidate-job'),
	'summary' : text(page,by_class % 'summary-info',select='//p')
}

def get_experiences(exprs):
	jobs = []
	for ex in exprs:
		fields = ex.xpath('div//*[span%s]' % (by_class[3:] % 'field-name'))
		job = {}
		for field in fields:
			content = field.xpath('span/text()')
			if len(content)<2:
				continue
			key = content[0]
			value = content[1:]
			value = ' '.join(value).replace('\n','').strip()
			if value:
				job[key] = value
		if job:
			jobs.append(job)
	return jobs

exp = page.xpath(by_class % 'job-experience-info' + by_class % 'container')
edu = page.xpath(by_class % 'education-info' + by_class % 'container')
cv['jobs']    = get_experiences(exp)
cv['schools'] = get_experiences(edu)
cv['skills']  = page.xpath(by_class % 'ability-tag' + '/text()')
print(json.dumps(cv,indent=4,ensure_ascii=False))


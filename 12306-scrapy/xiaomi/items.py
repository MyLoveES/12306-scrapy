# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html

import scrapy


class XiaomiItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()

    # url = scrapy.Field()
    # name = scrapy.Field()
    # price = scrapy.Field()
    # describe = scrapy.Field()
    # edition = scrapy.Field()
    # color = scrapy.Field()
    name = scrapy.Field()
    image_urls = scrapy.Field()
    url = scrapy.Field()
    pass

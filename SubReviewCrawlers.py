#encoding=utf-8
import json
import time
from bs4 import BeautifulSoup
from twisted.internet import reactor,defer
from twisted.web.client import getPage,downloadPage
from twisted.web.error import Error
from BaseReviewCrawler import BaseReviewCrawler

TIMEOUT = 5

class TaobaoCrawler(BaseReviewCrawler):

    def __init__(self):
        self.urlPrefix = 'http://rate.taobao.com/feedRateList.htm?'
        self.running = True
        self.jsonPath = "Json/Taobao/"
        self.title = ""
        self.itemId = ""
    
    def getItemTitle(self,soup):
        return soup.find(id="page").find(id="detail").find("h3").get_text().encode("utf-8")

    def crawlQueryParameters(self,soup):
        reviewUrl = soup.find("div",id="reviews",class_="J_DetailSection").get("data-listapi")
        #print soup.find("div",id="reviews",class_="J_DetailSection")
        print reviewUrl
        paramList = reviewUrl[reviewUrl.find("?")+1:].split("&")
        d = {}
        for param in paramList:
            p = param.split("=")
            d[p[0]] = p[1]
        for key in d.keys():
            if key not in ["userNumId","auctionNumId"]:
                d.pop(key)
        self.itemId = d['auctionNumId']
        return d
    
    @defer.deferredGenerator
    def getReviewsFromPage(self,title,params):
        
        def deferred1(page,cp):
            d = defer.Deferred()
            reactor.callLater(1,d.callback,self.parseReviewJson(page,cp))
            return d

        def deferred2(dataL,csvname):
            d = defer.Deferred()
            reactor.callLater(1,d.callback,self.writeToCSV(dataL,filename=csvname))
            return d
        
        cp = 1        
        #for cp in range(1,15000):
        while self.running:
            print cp
            params["currentPageNum"] = cp
            #info = self.getPageFromUrl('http://rate.taobao.com/feedRateList.htm?',params = params)
            url = self.generateReviewUrl(self.urlPrefix,params = params)

            while True:
                p = getPage(url,timeout=TIMEOUT)
                p.addErrback(self.getPageError,url = url)
                wfd = defer.waitForDeferred(p)
                yield wfd
                page = wfd.getResult()
                if isinstance(page,str):
                    break

            wfd = defer.waitForDeferred(deferred1(page,cp))
            yield wfd
            dataList = wfd.getResult()
            #wfd = defer.waitForDeferred(deferred2(dataList,title))
            wfd = defer.waitForDeferred(deferred2(dataList,params['auctionNumId']))
            yield wfd
            cp = cp+1

    def parseReviewJson(self,info,cp):
        dataL = []
        try:
            j = json.loads(unicode(info[info.find("(")+1:info.find(")",-1)-2].replace("\n",""),"gbk"))
        except Exception,e:
            print e
        self.writeJsonToFile(j,self.jsonPath+self.itemId,cp)

        if j["maxPage"] == j["currentPageNum"]:
            self.running = False
            return dataL
        for item in j["comments"]:
           # if len(item["content"]) < 15:
           #     continue
            d = {}
            d["id"] = item["rateId"]
            d["reviewContent"] = item["content"]
            d["reviewTime"] = item["date"]
            d["userNick"] = item["user"]["nick"]
            d["userId"] = unicode(item["user"]["userId"])
            d["userLink"] = item["user"]["nickUrl"]        
            d["appendReview"] = ""
            d["appendTime"] = ""
            d["appendId"] = ""
            if item["append"] is not None:
                d["appendId"] = item["append"]["appendId"]
                d["appendReview"] = item["append"]["content"]
                d["appendTime"] = item["append"]["dayAfterConfirm"]

            dataL.append(d)

        return dataL

class TmallCrawler(BaseReviewCrawler):

    def __init__(self):
        self.urlPrefix = "http://rate.tmall.com/list_detail_rate.htm?"
        self.jsonPath = "Json/Tmall/"
        self.title = ""
        self.itemId = ""
    
    def getItemTitle(self,soup):
        return soup.find(id="content").find(id="detail").find("a").get_text().encode("utf-8")

    def crawlQueryParameters(self,soup):     
        script = soup.find("form",id="J_FrmBid").find_next_sibling().get_text()
        d = {}
        d['spuId'] = self.findIdString(script,'spuId')
        d['sellerId'] = self.findIdString(script,'userId')
        d['itemId'] = self.findIdString(script,'itemId')
        self.itemId = d['itemId']
        return d

    def findIdString(self,script,string):
        start = script.find(string)
        quotation = script[start-1]
        idStart = script.find(quotation,script.find(":",start))
        sId = script[idStart+1:script.find(quotation,idStart+1)]
        return sId

    @defer.deferredGenerator
    def getReviewsFromPage(self,title,params):
        print "getReviewsFromPage"

        def deferred1(page,cp):
            d = defer.Deferred()
            reactor.callLater(1,d.callback,self.parseReviewJson(page,cp))
            return d

        def deferred2(dataL,csvname):
            d = defer.Deferred()
            reactor.callLater(1,d.callback,self.writeToCSV(dataL,filename=csvname))
            return d

        info = self.getPageFromUrl('http://rate.tmall.com/list_detail_rate.htm?',params = params)
        j = json.loads("{"+info+"}")
        currentPage = j["rateDetail"]["paginator"]["page"]
        lastPage = j["rateDetail"]["paginator"]["lastPage"]
        
        for cp in range(currentPage,lastPage):
            print cp
          
            params["currentPage"] = cp
            # info = self.getPageFromUrl('http://rate.tmall.com/list_detail_rate.htm?',params = params)
            url=self.generateReviewUrl(self.urlPrefix,params = params)        

            while True:
                p = getPage(url,timeout=TIMEOUT)
                p.addErrback(self.getPageError,url = url)
                wfd = defer.waitForDeferred(p)
                yield wfd
                page = wfd.getResult()
                if isinstance(page,str):
                    break

            wfd = defer.waitForDeferred(deferred1(page,cp))
            yield wfd
            dataList = wfd.getResult()
            wfd = defer.waitForDeferred(deferred2(dataList,self.itemId))
            yield wfd
           
    def parseReviewJson(self,info,cp):
        dataL = []
        j = json.loads("{"+unicode(info,"gbk")+"}")
        self.writeJsonToFile(j,self.jsonPath+self.itemId,cp)
        for item in j["rateDetail"]["rateList"]:
            d = {}
            if item["useful"]:
                #if item["dsr"] < 3:
                #    continue
               # if len(item["rateContent"]) < 15:
               #     continue
                d["id"] = item["id"]
                d["reviewContent"] = item["rateContent"]
                d["reviewTime"] = item["rateDate"]
                d["degree"] = item["dsr"]
                d["userNick"] = item["displayUserNick"]
                d["userId"] = unicode(item["displayUserNumId"])
                d["userLink"] = item["displayUserLink"]
                d["appendReview"] = ""
                d["appendTime"] = ""
                d["appendId"] = ""
                if len(item["appendComment"]) > 0:
                    d["appendId"] = item["appendComment"]["commentId"]
                    d["appendReview"] = item["appendComment"]["content"]
                    d["appendTime"] = item["appendComment"]["commentTime"]
                dataL.append(d)
               # print d["userNick"]
               # print d["userId"]
               # print d["reviewContent"]
               # print d["reviewTime"]
               # print "******************************************"
        return dataL

#crawler = TmallCrawler()
#crawler.crawl("http://detail.tmall.com/item.htm?id=14944940915")

#crawler2 = TaobaoCrawler()
#crawler2.crawl("http://item.taobao.com/item.htm?id=17180958841")

from xml.etree import ElementTree
from bs4 import BeautifulSoup as scrape
from pytube import YouTube
import requests
import sys
import yaml
import os

import memoryStore

# disable insecure http warning - we dont need heaps of callouts on networks that use their own self signing key.
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

EXPORTED_SUBSCRIPTIONS_FILE = "db/subscriptionsExport.xml"  # this needs to work from the original 'subscriptionsExport.xml' so it works as drag and drop
YTD_VIDEO_CLASS = "yt-uix-sessionlink yt-uix-tile-link spf-link yt-ui-ellipsis yt-ui-ellipsis-2"  # the html class that the videos are defined in on the page


def extractDataFromOPMLFile(filename):
    opmls = []
    names = []
    with open(filename, 'rt') as f:
        tree = ElementTree.parse(f)
    for node in tree.findall('.//outline'):
        opml = node.attrib.get('xmlUrl')
        name = node.attrib.get('title')
        if opml:
            opmls.append(opml)
        if name:
            names.append(name)

    opmlNames = memoryStore.opmlExtract(opmls, names)
    return opmlNames


def convertRSSToURL(opmls):
    urls = []

    for opml in opmls:
        fromPos = 52
        channelID = opml[fromPos:]
        urls.append("https://www.youtube.com/channel/" + channelID + "/videos")

    return urls


def indexUrl(channelURL):
    videos = []

    r = requests.get(channelURL, verify=False)
    page = r.text
    sc = scrape(page, 'html.parser')
    res = sc.find_all(attrs={'class': YTD_VIDEO_CLASS})

    for l in res:
        videos.append(l.get("href"))

    return videos


def doVideoIndex(metaURLs, nameList):
    indexedVideos = []
    count = 1
    for url in metaURLs:
        # Print out the latest stats, yes its ugly but its the best way for they

        sys.stdout.flush()
        sys.stdout.write("\rIndexing channel: " + url + " ({} of {})".format(count, len(metaURLs))
                         + " ChannelName = {}                            \r".format(nameList[count - 1]))
        sys.stdout.flush()

        result = indexUrl(url)
        indexedVideos.append(result)
        count += 1

    combinedResult = memoryStore.simpleData(metaURLs, nameList, indexedVideos)
    return combinedResult


def writeYAMLStringToFile(name, string, pos, total):
    with open(name + '.yt', "w+") as textFile:
        sys.stdout.flush()
        sys.stdout.write("\n Writing out cache file: {} ({} of {}) \n".format(name, pos + 1, total))
        sys.stdout.flush()
        textFile.write(string)


def generateYAMLString(channelURL, channelName, videos):
    data = memoryStore.simpleData(channelURL, channelName, videos)
    return yaml.dump(data)


def fromYAMLString(yamlString):
    return yaml.load(yamlString)


def readYAMLFile(filePath):
    fileData = open(filePath, 'r')
    return fileData.read()


# the mainish method that returns the array of channels, channel names and results
def getVideoIndex():
    extractedData = extractDataFromOPMLFile(EXPORTED_SUBSCRIPTIONS_FILE)
    OPMLList = extractedData.memOPMLS
    nameList = extractedData.memNames
    metaURLs = convertRSSToURL(OPMLList)

    results = doVideoIndex(metaURLs, nameList)
    return results


def writeCacheIndex(index):
    with open(index, "w+") as textFile:
        print('doesnt work yet')


def updateCache(results):
    urls = results.memChannels
    names = results.memNames
    videos = results.memVideos

    pos = 0

    sys.stdout.writelines("\n")

    for result in names:
        start = 32
        stop = 56

        dump = generateYAMLString(urls[pos], names[pos], videos[pos])
        key = urls[pos]
        key = key[start: stop]  # chops up the url so the channelID is just used to mark the file.
        fileName = 'cache/' + key + ".yt" + str(len(key))
        writeYAMLStringToFile(fileName, dump, pos, len(urls))

        pos += 1


def updateCacheFile(url, name, videos):
    start = 32
    stop = 56

    dump = generateYAMLString(url, name, videos)
    key = url[start: stop]  # chops up the url so the channelID is just used to mark the file.
    fileName = 'cache/' + key + ".yt" + str(len(key))
    writeYAMLStringToFile(fileName, dump, 0, 1)


def checkFileCount(dir):
    path, dirs, files = next(os.walk(dir))
    count = len(files)
    return count


def getNewChannelContent(data):
    start = 32
    stop = 56

    opmls = data.memOPMLS
    metaURLs = convertRSSToURL(opmls)

    downloadList = []
    genNewIndexForChannel = False

    for url in metaURLs:
        key = url[start: stop]  # chops up the url so the channelID is just used to mark the file.

        # fileName = '/cache/' + key + ".yt" + str(len(key)) primitive method that seeems to not work on windows or linux depending on how I join it

        fileName = os.path.join(os.getcwd() + '\cache', key + ".yt" + str(len(key)) + ".yt")

        yamlData = readYAMLFile(fileName)

        mem = fromYAMLString(yamlData)
        data = indexUrl(url)
        sys.stdout.flush()
        sys.stdout.write(
            "\rChecking url: {} for new videos.  ({} of {})".format(url, metaURLs.index(url), len(metaURLs)))

        for video in data:
            if video in mem.memVideos:
                # do nothing, this video has already been indexed
                pass
            else:
                # add it to the new array of videos to be downloaded
                downloadList.append(video)
                print("\nAdded: {} to download list. {} videos in list)".format(video, len(downloadList)))
                genNewIndexForChannel = True

        if genNewIndexForChannel:  # write out a new cache file with the updated channel meta
            updateCacheFile(url, mem.memNames, data)
            genNewIndexForChannel = False

    return downloadList


# on_progress_callback takes 4 parameters.
def video_progress_check(stream=None, chunk=None, file_handle=None, remaining=None):
    # Gets the percentage of the file that has been downloaded.
    percent = (100 * (file_size - remaining)) / file_size

    file = ""

    if percent == 100:
        file = "-> writing out file"

    sys.stdout.write("\r {:00.0f}% downloaded. ({}MB of {}MB) {}".format(percent, round(file_size / 1000000 - remaining / 1000000, 1), round(file_size / 1000000, 1), file))
    sys.stdout.flush()


def downloadFromList(down, store, path):
    for watchID in down:
        httpURL = 'https://www.youtube.com' + watchID
        global file_size
        yt = YouTube(httpURL, on_progress_callback=video_progress_check)
        video = yt.streams.first()
        file_size = video.filesize
        print("\n Downloading video '{}' to {}".format(httpURL, path))
        video.download(path)


cacheAmount = checkFileCount('cache/')
extractedData = extractDataFromOPMLFile(EXPORTED_SUBSCRIPTIONS_FILE)

print("Found {} cache files out of {} channel entries.".format(cacheAmount, len(extractedData.memOPMLS)))
check = input("Would you like to update video cache now? {} files to be updated (y/n): ".format(cacheAmount))
check = check.replace(" ", "")

if check == "y":
    videoData = getVideoIndex()
    updateCache(videoData)

if check == "n":
    print("Checking channels for new content!")
    # do download and check stuff here
    downloads = getNewChannelContent(extractedData)
    vidLen = len(downloads)
    global store
    store = memoryStore.dbCacheVideo(downloads, 0)

    print("\n {} videos to be updated!".format(vidLen))

    if vidLen > 0:
        continueDL = input("Begin downloading {} videos? (y/n): ".format(vidLen))

        if continueDL == "y":
            downloadFromList(downloads, store, "download/")
        else:
            print("Exiting..")
    else:
        print("No new videos found, exiting...")

else:
    print("Invalid option '{}' exiting".format(check))

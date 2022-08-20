# thumbnail_maker.py
import time
import os
import logging
from urllib.parse import urlparse
from urllib.request import urlretrieve
from queue import Queue
from threading import Thread
import PIL
from PIL import Image
FORMAT = "[%(threadName)s, %(asctime)s, %(levelname)s] %(message)s"
logging.basicConfig(filename='logfile.log', level=logging.DEBUG, format=FORMAT, force=True)

class ThumbnailMakerService(object):
    def __init__(self, home_dir='.'):
        self.home_dir = home_dir
        self.input_dir = self.home_dir + os.path.sep + 'incoming'
        self.output_dir = self.home_dir + os.path.sep + 'outgoing'
        self.img_queue = Queue()
        self.dl_queue = Queue()


    def download_image(self):
        # Go into the loop and read messages of the queue instead of going into infinite loop lets loop until the download queue is empty
        while not self.dl_queue.empty():
            try:
              url = self.dl_queue.get(block=False)
              # download each image and save to the input dir
              img_filename = urlparse(url).path.split('/')[-1]
              urlretrieve(url, self.input_dir + os.path.sep + img_filename)
              self.img_queue.put(img_filename)  # pop the file name for the file just downloaded into the queue
              #need to mark task is done for every url we get of the queue
              self.dl_queue.task_done()

            except Queue.Empty:
                logging.info("Queue is empty")


    def download_images(self, img_url_list):
        # validate inputs
        if not img_url_list:
            return
        os.makedirs(self.input_dir, exist_ok=True)
        
        logging.info("beginning image downloads")

        start = time.perf_counter()
        for url in img_url_list:
            # download each image and save to the input dir 
            img_filename = urlparse(url).path.split('/')[-1]
            urlretrieve(url, self.input_dir + os.path.sep + img_filename)
            self.img_queue.put(img_filename) # pop the file name for the file just downloaded into the queue
        end = time.perf_counter()

        self.img_queue.put(None)

        logging.info("downloaded {} images in {} seconds".format(len(img_url_list), end - start))

    def perform_resizing(self):
        # validate inputs
        #don't need this since reading of the queue not a filesystem & that will check the file system before it runs
        # if not os.listdir(self.input_dir):
        #     return
        os.makedirs(self.output_dir, exist_ok=True)

        logging.info("beginning image resizing")
        target_sizes = [32, 64, 200]
        num_images = len(os.listdir(self.input_dir))

        start = time.perf_counter()
        #for filename in os.listdir(self.input_dir): instead of reading a folder go into the loop
        #need to use poison pill technique to exit infinite loop (by putting special message into the queue so when the resize thread receives the message, it can exit the loop and terminate.
        while True:
            # in the loop read a file from the queue
            filename = self.img_queue.get()
            if filename:
                logging.info("resizing image {} ".format(filename))
                orig_img = Image.open(self.input_dir + os.path.sep + filename)
                for basewidth in target_sizes:
                    img = orig_img
                    # calculate target height of the resized image to maintain the aspect ratio
                    wpercent = (basewidth / float(img.size[0]))
                    hsize = int((float(img.size[1]) * float(wpercent)))
                    # perform resizing
                    img = img.resize((basewidth, hsize), PIL.Image.LANCZOS)

                    # save the resized image to the output dir with a modified file name
                    new_filename = os.path.splitext(filename)[0] + \
                        '_' + str(basewidth) + os.path.splitext(filename)[1]
                    img.save(self.output_dir + os.path.sep + new_filename)

                os.remove(self.input_dir + os.path.sep + filename)
                logging.info("done")
                self.img_queue.task_done()
            else:
                self.img_queue.task_done()
                break
        end = time.perf_counter()

        logging.info("created {} thumbnails in {} seconds".format(num_images, end - start))

    def make_thumbnails(self, img_url_list):
        logging.info("START make_thumbnails")
        start = time.perf_counter()

        #Loading all the URLs into download queue
        for img_url in img_url_list:
            self.dl_queue.put(img_url)

        num_dl_treads = 4
        for _ in range(num_dl_treads):
            t = Thread(target=self.download_image)
            t.start()

        # t1 = Thread(target=self.download_images, args=([img_url_list]))
        t2 = Thread(target=self.perform_resizing)
        t2.start()

        self.dl_queue.join()
        self.img_queue.put(None)
        t2.join()

        end = time.perf_counter()
        logging.info("END make_thumbnails in {} seconds".format(end - start))
    
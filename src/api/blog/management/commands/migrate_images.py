import os
import requests
import json
from django.core.management.base import BaseCommand, CommandError
from blog.models import *
from filebrowser.sites import site
from filebrowser.base import FileListing,FileObject
from django.core.files.images import ImageFile
from django.core.files.base import ContentFile
import requests
import re
import shutil

## for future reference, per https://django-filebrowser.readthedocs.io/en/latest/filelisting.html
### this will get all the file objects in my uploads folder
# 		def filter_listing(item):
# 			return item.filetype != "Folder"
# 		filelisting=FileListing(site.directory,filter_func=filter_listing)
# 		for f in filelisting.files_walk_filtered():
# 			print(f)


class Command(BaseCommand):
	help = 'pulls the images uploaded to the sv blog & alters the pointers in the posts'
	def handle(self, *args, **options):
		
		def download_sv_img(fpath,baseurl):
			fname=os.path.basename(fpath)
			r = requests.get(baseurl+fpath, stream=True)
			print(r.status_code)
			if r.status_code == 200:
				new_fpath=os.path.join(site.storage.location,site.directory,fname)
# 				with open(new_fpath, 'wb') as f:
# 					r.raw.decode_content = True
# 					shutil.copyfileobj(r.raw, f)
				return new_fpath
			else:
				print("could not find",baseurl+fpath)
				return None
# 		
# 		
# 		sv_blogimages_baseurl="https://www.slavevoyages.org/documents/"
# 		
# 		#1. pull the thumbnails
# 		#IF SUCCESSFUL, THIS WILL ONLY HIT 400'S AFTER THE FIRST RUN
# 		posts=Post.objects.all()
# 		for post in posts:
# 			post_thumbnail=post.thumbnail
# 			fpath_str=str(post_thumbnail)
# 			new_img_fpath=download_sv_img(fpath_str,sv_blogimages_baseurl)
# 			if new_img_fpath is not None:
# 				fo=FileObject(new_img_fpath)
# 				post.thumbnail=fo
# 				post.save()
		
		#2. pull the <img> tags
		
		sv_baseurl="https://www.slavevoyages.org/"
		posts=Post.objects.all()
		for post in posts:
			running=False
			post_content=post.content
			imgs=re.findall("<img\s+src\s*=\s*\".+?(?=\")",post_content)
			imgs_clean=[]
			for i in imgs:
				clean=re.sub(".*?/(?=documents/)","",i)
				clean=re.sub(".*?/(?=static/)","",clean)
				imgs_clean.append([i,clean])
			for img_clean in imgs_clean:
				orig,clean=img_clean
				new_img_fpath=download_sv_img(clean,sv_baseurl)
				if new_img_fpath is not None:
					print(orig,clean,new_img_fpath)
					post_content=post_content.replace(orig,'<img src="/'+new_img_fpath)
					running=True
				else:
					print("no dice")
			if running:
				print(post)
				post.content=post_content
				post.save()

		
# 		authors=Author.objects.all()
# 		for author in authors:
# 			author_photo=author.photo
# 			author_photo_str=str(author_photo)
# 			author.photo=None
# 			author.save()
# 			if author_photo not in [None,""]:
# 				new_img_fpath=download_sv_img(author_photo_str,sv_blogimages_baseurl)
# 				fo=FileObject(new_img_fpath)
# 				author.photo=fo
# 				author.save()
		
		
		
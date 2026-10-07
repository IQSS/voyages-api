from rest_framework import serializers
from rest_framework.fields import SerializerMethodField,IntegerField,CharField,Field
import re
from .models import *
from document.models import *
from geo.models import *
from .models import *
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from common.static.Post_options import Post_options
from common.static.Author_options import Author_options
from common.static.Institution_options import Institution_options
from common.autocomplete_indices import get_all_model_autocomplete_fields
import re
from voyages3.settings import site_storage_base_url
from voyages3.localsettings import OPEN_API_BASE_URL

class AuthorInstitutionSerializer(serializers.ModelSerializer):
	class Meta:
		model=Institution
		fields='__all__'

class PostAuthorSerializer(serializers.ModelSerializer):
	photo = serializers.SerializerMethodField('get_photo_url')
	institution = AuthorInstitutionSerializer(many=False)
	@extend_schema_field(serializers.CharField)
	def get_photo_url(self, obj) -> str:
		if obj.photo not in ["",None]:
			return obj.photo.url
	class Meta:
		model=Author
		fields='__all__'

class TagSerializer(serializers.ModelSerializer):
	class Meta:
		model=Tag
		fields='__all__'

def media_uploads_sub(html):
	'''
		blog posts are composed in the tinymce editor and can use the filebrowser plugin
		to upload assets, such as images. when these are embedded in the html, they are
		recorded with relative paths. as a result, the front-end looks, for instance, for
		an image in the blog post at the front-end site, naturally, rather than here. we
		rewrite the html before returning it (until i can find a better system).
	'''
	site_storage_base_url_no_leading_slash=re.sub("^/","",site_storage_base_url)
	media_uploads_baseurl=f"{OPEN_API_BASE_URL}{site_storage_base_url_no_leading_slash}"
	clean_html=re.sub(f"(?<=src=\").*?{site_storage_base_url}",media_uploads_baseurl,html)
	clean_html=re.sub(f"(?<=href=\").*?{site_storage_base_url}",media_uploads_baseurl,clean_html)
	return clean_html

class PostSerializer(serializers.ModelSerializer):
	authors = PostAuthorSerializer(many=True,read_only=True)
	tags = TagSerializer(many=True,read_only=True)
	thumbnail = serializers.SerializerMethodField('get_thumbnail_url')
	content = serializers.SerializerMethodField('get_content')
	@extend_schema_field(serializers.CharField)
	def get_thumbnail_url(self, obj) -> str:
		if obj.thumbnail not in ["",None]:
			return obj.thumbnail.url
	def get_content(self, obj):
		return media_uploads_sub(obj.content)
	
	class Meta:
		model=Post
		fields='__all__'

class AuthorPostSerializer(serializers.ModelSerializer):
	tags = TagSerializer(many=True,read_only=True)
	thumbnail = serializers.SerializerMethodField('get_thumbnail_url')
	@extend_schema_field(serializers.CharField)
	def get_thumbnail_url(self, obj) -> str:
		if obj.thumbnail not in ["",None]:
			return obj.thumbnail.url
	class Meta:
		model=Post
		exclude=['authors',]

class AuthorSerializer(serializers.ModelSerializer):
	posts = AuthorPostSerializer(many=True,read_only=True)
	photo = serializers.SerializerMethodField('get_photo_url')
	institution = AuthorInstitutionSerializer(many=False)
	@extend_schema_field(serializers.CharField)
	def get_photo_url(self, obj) -> str:
		if obj.photo not in ["",None]:
			return obj.photo.url
	class Meta:
		model=Author
		fields='__all__'

class InstitutionSerializer(serializers.ModelSerializer):
	institution_authors=AuthorSerializer(many=True)
	class Meta:
		model=Institution
		fields='__all__'

############ REQUEST FIILTER OBJECTS
class AnyField(Field):
	def to_representation(self, value):
		return value

	def to_internal_value(self, data):
		return data

class PostFilterItemSerializer(serializers.Serializer):
	op=serializers.ChoiceField(choices=["in","gte","lte","exact","icontains","btw","andlist"])
	varName=serializers.ChoiceField(choices=[k for k in Post_options])
	searchTerm=AnyField()

class AuthorFilterItemSerializer(serializers.Serializer):
	op=serializers.ChoiceField(choices=["in","gte","lte","exact","icontains","btw","andlist"])
	varName=serializers.ChoiceField(choices=[k for k in Author_options])
	searchTerm=AnyField()

class InstitutionFilterItemSerializer(serializers.Serializer):
	op=serializers.ChoiceField(choices=["in","gte","lte","exact","icontains","btw","andlist"])
	varName=serializers.ChoiceField(choices=[k for k in Institution_options])
	searchTerm=AnyField()

########### PAGINATED VOYAGE LISTS 
@extend_schema_serializer(
	examples = [
         OpenApiExample(
			'Paginated filtered blog req.',
			summary='Paginated filtered blog req.',
			description='Here, we request blog posts tagged as "Texas Bound" or "Lesson Plan"',
			value={
			  "filter": [
					{
						"varName":"tags__name",
						"searchTerm":[
							"Texas Bound",
							"Lesson Plan"
						],
						"op":"in"
					}
				],
				"page": 0,
				"page_size": 12
			},
			request_only=True
		)
    ]
)
class PostListRequestSerializer(serializers.Serializer):
	page=serializers.IntegerField(required=False,allow_null=True)
	page_size=serializers.IntegerField(required=False,allow_null=True)
	filter=PostFilterItemSerializer(many=True,allow_null=True,required=False)
	order_by=serializers.ListField(child=serializers.CharField(allow_null=True),required=False,allow_null=True)
	global_search=serializers.CharField(allow_null=True,required=False)
	
class PostListResponseSerializer(serializers.Serializer):
	page=serializers.IntegerField()
	page_size=serializers.IntegerField()
	count=serializers.IntegerField()
	results=PostSerializer(many=True,read_only=True)

@extend_schema_serializer(
	examples = [
         OpenApiExample(
			'Paginated filtered blog authors list req.',
			summary='Paginated filtered blog authors list req.',
			description='Here, we are searching for authors who have written posts with the tag Introductory Maps',
			value={
			  "filter": [
					{
						"varName":"posts__tags__name",
						"searchTerm":[
							"Introductory Maps"
						],
						"op":"in"
					}
				],
				"page": 0,
				"page_size": 12
			},
			request_only=True
		)
    ]
)
class AuthorListRequestSerializer(serializers.Serializer):
	page=serializers.IntegerField(required=False,allow_null=True)
	page_size=serializers.IntegerField(required=False,allow_null=True)
	filter=AuthorFilterItemSerializer(many=True,allow_null=True,required=False)
	order_by=serializers.ListField(child=serializers.CharField(allow_null=True),required=False,allow_null=True)
	
class AuthorListResponseSerializer(serializers.Serializer):
	page=serializers.IntegerField()
	page_size=serializers.IntegerField()
	count=serializers.IntegerField()
	results=AuthorSerializer(many=True,read_only=True)

@extend_schema_serializer(
	examples = [
         OpenApiExample(
			'Paginated filtered blog institution req.',
			summary='Paginated filtered blog institution req.',
			description='Here, we are searching for instutions whose authors wrote blog posts that have the tag Introductory Maps',
			value={
			  "filter": [
					{
						"varName":"institution_authors__posts__tags__name",
						"searchTerm":[
							"Introductory Maps"
						],
						"op":"in"
					}
				],
				"page": 0,
				"page_size": 12
			},
			request_only=True
		)
    ]
)
class InstitutionListRequestSerializer(serializers.Serializer):
	page=serializers.IntegerField(required=False,allow_null=True)
	page_size=serializers.IntegerField(required=False,allow_null=True)
	filter=InstitutionFilterItemSerializer(many=True,allow_null=True,required=False)
	order_by=serializers.ListField(child=serializers.CharField(allow_null=True),required=False,allow_null=True)
	
class InstitutionListResponseSerializer(serializers.Serializer):
	page=serializers.IntegerField()
	page_size=serializers.IntegerField()
	count=serializers.IntegerField()
	results=InstitutionSerializer(many=True,read_only=True)


############ AUTOCOMPLETE SERIALIZERS
@extend_schema_serializer(
	examples = [
         OpenApiExample(
			'Paginated autocomplete on blog post tags',
			summary='Paginated autocomplete on blog post tags',
			description='Here, we are requesting the first 10 suggested values of blog tags like "ma"',
			value={
				"varName": "tags__name",
				"querystr": "ma",
				"offset": 0,
				"limit": 10,
				"filter": []
			}
		)
    ]
)
class PostAutoCompleteRequestSerializer(serializers.Serializer):
	varName=serializers.ChoiceField(choices=get_all_model_autocomplete_fields('Post'))
	querystr=serializers.CharField(allow_null=True,allow_blank=True)
	offset=serializers.IntegerField()
	limit=serializers.IntegerField()
	filter=PostFilterItemSerializer(many=True,allow_null=True,required=False)

class PostAutoCompletekvSerializer(serializers.Serializer):
	value=serializers.CharField()

class PostAutoCompleteResponseSerializer(serializers.Serializer):
	suggested_values=PostAutoCompletekvSerializer(many=True)

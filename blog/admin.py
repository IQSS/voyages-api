from django.contrib import admin
from django import forms

from blog.models import *


# class AdvancedEditorManager(forms.Textarea):
# 
#     class Media:
#         js = (
#             '//cdn.tiny.cloud/1/evau54786a4pxb62mp84sjc26h72hrpdu9b5'
#             'ht3zzn8oisd5/tinymce/5/tinymce.min.js',
#             'scripts/filebrowser/TinyMCEv5Admin.js')
# 
#     def __init__(self, language=None, attrs=None):
#         self.language = language or settings.LANGUAGE_CODE[:2]
#         self.attrs = {'class': 'advancededitormanager'}
#         if attrs:
#             self.attrs.update(attrs)
#         super().__init__(attrs)
# 
#     def render(self, name, value, attrs=None):
#         rendered = super().render(name, value, attrs)
#         return rendered
# 
# class AdvancedEditor(forms.Textarea):
# 
#     class Media:
#         js = (
#             '//cdn.tiny.cloud/1/evau54786a4pxb62mp84sjc26h72hrpdu9b5'
#             'ht3zzn8oisd5/tinymce/5/tinymce.min.js',
#             'scripts/tiny_mce/textareas_small.js')
# 
#     def __init__(self, language=None, attrs=None):
#         self.language = language or settings.LANGUAGE_CODE[:2]
#         self.attrs = {'class': 'advancededitor'}
#         if attrs:
#             self.attrs.update(attrs)
#         super().__init__(attrs)
# 
#     def render(self, name, value, attrs=None):
#         rendered = super().render(name, value, attrs)
#         return rendered

class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'language', 'status','created_on')
    list_filter = ("status",)
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}
#     change_list_template = 'blog/admin/post_change_list.html'
    
#     formfield_overrides = {
#         models.TextField: {'widget': AdvancedEditorManager(
#         attrs={'class': 'tinymcetextareamanager'})}
#     }
# 
#     add_form_template = 'blog/admin/change_form.html'
#     change_form_template = 'blog/admin/change_form.html'


    
    def make_published(self,request,queryset):
        rows_updated = queryset.update(status=PUBLISH_STATUS)
        if rows_updated == 1:
            message_count = "1 post was"
        else:
            message_count = "%s post were" % rows_updated

        self.message_user(request,"%s successfully marked as published." % message_count)


    def make_draft(self,request,queryset):
        rows_updated = queryset.update(status=DRAFT_STATUS)
        if rows_updated == 1:
            message_count = "1 post was"
        else:
            message_count = "%s post were" % rows_updated

        self.message_user(request,"%s successfully marked as draft." % message_count)

    
    def force_translation(self,request,queryset):
        total = 0

        for instance in queryset.all():
            
            for lang_code, _ in settings.LANGUAGES:            
                # First check if the target language already has a translation. 
                existing = Post.objects.filter(slug=instance.slug, language=lang_code)
                
                count = existing.count()

                if count > 0: #update
                    clone = existing[0]
                    authors = clone.authors.all()                    
                    tags = clone.tags.all()

                else: #add new
                    clone = Post.objects.get(pk=instance.pk)

                    authors = clone.authors.all()
                    tags = clone.tags.all()

                    clone.pk = None

                if not clone.title in [None, '']:
                    clone.title = translate_text(lang_code, instance.title)

                if not clone.subtitle in [None, '']:
                    clone.subtitle = translate_text(lang_code, instance.subtitle)

                if not clone.content in [None, '']:
                    clone.content = translate_text(lang_code, instance.content)

                clone.language = lang_code

                clone.save()                
                
                clone.authors.set(authors)
                clone.tags.set(tags) 

                total += 1

        if total == 1:
            message_count = "1 post was"
        else:
            message_count = "%s post were" % total


        self.message_user(request,"%s translated." % message_count)

    force_translation.short_description = 'FORCE TRANSLATION'
    
        
    def translate_to_new_languages(self,request,queryset):

        total = 0

        for instance in queryset.all():
            
            for lang_code, _ in settings.LANGUAGES:            
                # First check if the target language already has a translation.
                count = Post.objects.filter(slug=instance.slug, language=lang_code).count()
                if count > 0:
                    continue

                clone = Post.objects.get(pk=instance.pk)

                authors = clone.authors.all()
                tags = clone.tags.all()

                clone.pk = None

                if not clone.title in [None, '']:
                    clone.title = translate_text(lang_code, instance.title)

                if not clone.subtitle in [None, '']:
                    clone.subtitle = translate_text(lang_code, instance.subtitle)

                if not clone.content in [None, '']:
                    clone.content = translate_text(lang_code, instance.content)

                clone.language = lang_code

                clone.save()                
                
                clone.authors.set(authors)
                clone.tags.set(tags) 

                total += 1

        if total == 1:
            message_count = "1 post was"
        else:
            message_count = "%s post were" % total


        self.message_user(request,"%s translated." % message_count)
        


    def get_urls(self):
        urls = super(PostAdmin, self).get_urls()
        
        return urls
        
    actions = [make_published,make_draft,translate_to_new_languages,force_translation]

class TagAdmin(admin.ModelAdmin):
	
	fields='__all__'

    

class InstitutionAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug':('name',)}

class AuthorAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug':('name',)}




admin.site.register(Post, PostAdmin)

admin.site.register(Tag)

admin.site.register(Institution,InstitutionAdmin)

admin.site.register(Author,AuthorAdmin)
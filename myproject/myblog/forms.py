from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MaxLengthValidator
from django.utils.functional import cached_property
from parler.forms import TranslatableModelForm
from taggit_autosuggest.widgets import TagAutoSuggest
from django.utils.translation import get_language, gettext, gettext_lazy as _

from .models import BlogCategory, BlogConfig, Post, AuthorEntriesPlugin

PERMALINK_TYPE_CATEGORY = "category"
META_DESCRIPTION_LENGTH = 320
PLUGIN_TEMPLATE_FOLDERS = (("plugins", _("Default template")),)
META_TITLE_LENGTH = 70

User = get_user_model()


class ConfigFormBase:
    """Base form class for all models depends on app_config."""

    @cached_property
    def app_config(self):
        """
        Return the currently selected app_config, whether it's an instance attribute or passed in the request
        """
        if getattr(self.instance, "app_config_id", None):
            return self.instance.app_config
        elif "app_config" in self.initial:
            return BlogConfig.objects.get(pk=self.initial["app_config"])
        elif self.data.get("app_config", None):
            return BlogConfig.objects.get(pk=self.data["app_config"])
        return None


class CategoryAdminForm(ConfigFormBase, TranslatableModelForm):
    def __init__(self, *args, **kwargs):
        self.base_fields["meta_description"].validators = [MaxLengthValidator(META_DESCRIPTION_LENGTH)]
        original_attrs = self.base_fields["meta_description"].widget.attrs
        if "cols" in original_attrs:
            del original_attrs["cols"]
        if "rows" in original_attrs:
            del original_attrs["rows"]
        original_attrs["maxlength"] = "META_DESCRIPTION_LENGTH"
        self.base_fields["meta_description"].widget = forms.TextInput(original_attrs)
        super().__init__(*args, **kwargs)

        if "parent" in self.fields:
            qs = self.fields["parent"].queryset
            if self.instance.pk:
                qs = qs.exclude(pk__in=[self.instance.pk] + [child.pk for child in self.instance.descendants()])
            config = None
            if getattr(self.instance, "app_config_id", None):
                qs = qs.namespace(self.instance.app_config.namespace)
            elif "app_config" in self.initial:
                config = BlogConfig.objects.get(pk=self.initial["app_config"])
            elif self.data.get("app_config", None):
                config = BlogConfig.objects.get(pk=self.data["app_config"])
            if config:
                qs = qs.namespace(config.namespace)
            self.fields["parent"].queryset = qs

    class Meta:
        model = BlogCategory
        fields = "__all__"


class BlogPluginForm(forms.ModelForm):
    """Base plugin form to inject the list of configured template folders from BLOG_PLUGIN_TEMPLATE_FOLDERS."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "template_folder" in self.fields:
            self.fields["template_folder"].choices = PLUGIN_TEMPLATE_FOLDERS


class LatestEntriesForm(BlogPluginForm):
    """Custom forms for BlogLatestEntriesPlugin to properly load taggit-autosuggest."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tags"].widget = TagAutoSuggest("taggit.Tag")

    class Media:
        css = {"all": ("{}myblog/css/{}".format(settings.STATIC_URL, "myblog_admin.css"),)}


class AuthorPostsForm(BlogPluginForm):
    """Custom form for BlogAuthorPostsPlugin to apply distinct to the list of authors in plugin changeform."""

    '''
    Choices are: authorentriesplugin, created_usergroups, created_users, date_joined, djangocms_usersettings, email, filer_clipboards, filer_folder_permissions, filer_owned_folders, first_name, globalpagepermission, groups, id, is_active, is_staff, is_superuser, last_login, last_name, logentry, owned_files, pagepermission, pageuser, password, post_author, user_permissions, username

    '''
    def __init__(self, *args, **kwargs):
        super(AuthorPostsForm, self).__init__(*args, **kwargs)
        # apply distinct due to django issue #11707
        qs = User.objects.filter(is_staff=True).distinct()
        #qs = Pos.objects.filter(author_id=my_model.other).distinct()
        self.fields["authors"].queryset  = qs


class PostAdminFormBase(ConfigFormBase, TranslatableModelForm):
    """
    Common methods between the admin and wizard form
    """

    class Meta:
        model = Post
        fields = "__all__"

    @cached_property
    def available_categories(self):
        qs = BlogCategory.objects

        if self.app_config:
            return qs.namespace(self.app_config.namespace).active_translations()
        return qs

    def _post_clean_translation(self, translation):
        # This is a quickfix for https://github.com/django-parler/django-parler/issues/236
        # which needs to be fixed in parler
        # operating at form level ensure that if the model is validated outside the form
        # the uniqueness check is not disabled
        super()._post_clean_translation(translation)
        self._validate_unique = False


class PostAdminForm(PostAdminFormBase):
    def __init__(self, *args, **kwargs):
        self.base_fields["meta_description"].validators = [MaxLengthValidator(META_DESCRIPTION_LENGTH)]
        original_attrs = self.base_fields["meta_description"].widget.attrs
        if "cols" in original_attrs:
            del original_attrs["cols"]
        if "rows" in original_attrs:
            del original_attrs["rows"]
        original_attrs["maxlength"] = META_DESCRIPTION_LENGTH
        self.base_fields["meta_description"].widget = forms.TextInput(original_attrs)
        self.base_fields["meta_title"].validators = [MaxLengthValidator(META_TITLE_LENGTH)]
        super().__init__(*args, **kwargs)
        if "categories" in self.fields:
            if self.app_config and self.app_config.url_patterns == PERMALINK_TYPE_CATEGORY:
                self.fields["categories"].required = True
            self.fields["categories"].queryset = self.available_categories

        if "app_config" in self.fields:
            # Don't allow app_configs to be added here. The correct way to add an
            # apphook-config is to create an apphook on a cms Page.
            self.fields["app_config"].widget.can_add_related = False

        if self.app_config:
            if not self.initial.get("main_image_full", ""):
                self.initial["main_image_full"] = self.app_config.app_data["config"].get("default_image_full")
            if not self.initial.get("main_image_thumbnail", ""):
                self.initial["main_image_thumbnail"] = self.app_config.app_data["config"].get(
                    "default_image_thumbnail"
                )

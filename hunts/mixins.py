from django.utils.decorators import method_decorator
from lazysignup.decorators import allow_lazy_user


class LazyLoginMixin:
    @method_decorator(allow_lazy_user)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

from lazysignup.decorators import allow_lazy_user


class LazyLoginMixin:
    @allow_lazy_user
    def dispatch(self, *args, **kwargs):
        super().dispatch(self, *args, **kwargs)

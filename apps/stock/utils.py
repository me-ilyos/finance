from django.shortcuts import redirect
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages

# Admin check function
def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

# Admin required mixin for class-based views
class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return is_admin(self.request.user)
    
    def handle_no_permission(self):
        messages.error(self.request, "Access restricted to admin users only.")
        return redirect('login') 
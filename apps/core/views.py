from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views import View
from .forms import LoginForm

# Create your views here.

class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        form = LoginForm()
        return render(request, 'login.html', {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
            else:
                # Add error message for invalid credentials
                form.add_error(None, "Foydalanuvchi nomi yoki parol noto'g'ri.")
        return render(request, 'login.html', {'form': form})

@login_required
def dashboard_view(request):
    return render(request, 'dashboard.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

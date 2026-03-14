from django.shortcuts import render
from django.http import Http404
import os
from django.conf import settings

def index(request):
    return render(request, 'index.html')

def serve_html(request, page):
    # Construct the potential template path
    template_name = f"{page}.html"
    
    # Check if the template exists in the frontend directory
    # (Django render will look in TEMPLATES DIRS)
    try:
        return render(request, template_name)
    except Exception:
        raise Http404("Page not found")

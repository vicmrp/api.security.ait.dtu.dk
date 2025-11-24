from django.http import HttpResponse

def hello_world(request, computer_dns_name):
    return HttpResponse("Hello, World!")
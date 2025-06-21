from django.shortcuts import render

# Create your views here.
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST

@require_POST
def add_one(request):
    try:
        body = json.loads(request.body)
        number = body.get('number')
        if not isinstance(number, int):
            return JsonResponse({'error': 'number must be an integer'}, status=400)
        return JsonResponse({'result': number + 1})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

import base64
import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .services import process_uploaded_files, strip_numeric_suffix

ALLOWED_EXTENSIONS = (".json", ".csv")
MAX_FILES = 50


@login_required
def index(request):
    return render(request, 'anonimrussia/index.html', context={'title': 'Обезличивание данных'})


@login_required
@require_POST
def process_files(request):
    uploaded_files = request.FILES.getlist('files')

    if not uploaded_files:
        return JsonResponse({"error": "Файлы не были переданы"}, status=400)

    if len(uploaded_files) > MAX_FILES:
        return JsonResponse(
            {"error": f"Слишком много файлов за раз (максимум {MAX_FILES})"},
            status=400,
        )

    for f in uploaded_files:
        clean_name = strip_numeric_suffix(f.name)
        if not clean_name.lower().endswith(ALLOWED_EXTENSIONS):
            return JsonResponse(
                {"error": f"Недопустимый тип файла: {f.name}. Разрешены только .json и .csv"},
                status=400,
            )

    def stream():
        for event in process_uploaded_files(uploaded_files):
            if event["type"] == "log":
                yield json.dumps({"type": "log", "message": event["message"]}, ensure_ascii=False) + "\n"
            elif event["type"] == "result":
                zip_b64 = base64.b64encode(event["zip_bytes"]).decode("ascii")
                yield json.dumps(
                    {"type": "result", "zip_base64": zip_b64, "summary": event["summary"]},
                    ensure_ascii=False,
                ) + "\n"

    response = StreamingHttpResponse(stream(), content_type='application/x-ndjson')
    response['X-Accel-Buffering'] = 'no'
    response['Cache-Control'] = 'no-cache'
    return response
from datetime import timedelta

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import BackgroundJob
from .services import (
    IdempotencyConflict,
    JobQueueUnavailable,
    enqueue_job,
    job_data,
)


def queue_job_response(request, job_type, payload):
    try:
        job, _created = enqueue_job(
            request.user,
            job_type,
            payload,
            idempotency_key=request.headers.get('Idempotency-Key'),
        )
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except IdempotencyConflict as exc:
        return Response({'error': str(exc)}, status=status.HTTP_409_CONFLICT)
    except JobQueueUnavailable:
        return Response(
            {'error': 'Background processing is unavailable. Please try again later.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    response_status = status.HTTP_202_ACCEPTED if job.status in ('queued', 'running') else status.HTTP_200_OK
    return Response(job_data(job), status=response_status)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def job_status(request, job_id):
    job = BackgroundJob.objects.filter(pk=job_id, user=request.user).first()
    if job is None:
        return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Report lost workers instead of leaving a spinner forever. Sending jobs
    # are deliberately not auto-replayed: delivery may have happened before a
    # worker or network failure, so the owner must verify before retrying.
    stale_after = timedelta(minutes=20 if job.status == 'running' else 75)
    anchor = job.started_at if job.status == 'running' else job.created_at
    if job.status in ('queued', 'running') and anchor and anchor < timezone.now() - stale_after:
        stale_filter = BackgroundJob.objects.filter(pk=job.pk, user=request.user, status=job.status)
        stale_filter = stale_filter.filter(
            started_at__lt=timezone.now() - stale_after
        ) if job.status == 'running' else stale_filter.filter(
            created_at__lt=timezone.now() - stale_after
        )
        stale_filter.update(
            status='failed',
            error=(
                'The worker stopped reporting progress. Check the mailbox/provider before retrying, '
                'because an external send may already have completed.'
            ),
            finished_at=timezone.now(),
        )
        job.refresh_from_db()

    return Response(job_data(job))

from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)


class CsrfLoggingMiddleware(MiddlewareMixin):
    """
    Логирует ошибки CSRF для отладки
    Используется только в режиме разработки
    """

    def process_response(self, request, response):
        try:
            reason = getattr(request, 'csrf_processing_failed_reason', None)
            if reason:
                user = getattr(request, 'user', None)
                user_id = getattr(user, 'id', None) if user else None
                logger.warning('CSRF ошибка на %s (user=%s): %s', request.path, user_id, reason)
        except Exception:
            # Не падаем если что-то пошло не так
            logger.exception('Ошибка при логировании CSRF')
        return response

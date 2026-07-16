"""
tests/test_notifier.py
속보 이슈 → 카테고리 구독자 알림 발송 — mock 기반 검증
"""
import uuid
from unittest.mock import MagicMock, patch

from app.db.notifier import _send_breaking_email, notify_breaking_issues
from app.models.category import Category
from app.models.user import User


def _mock_session_ctx():
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx


def _execute_result(items):
    return MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=items))))


class TestNotifyBreakingIssues:

    def test_대상_이슈_없으면_0_반환(self):
        with patch("app.db.notifier.get_session") as mock_session:
            mock_ctx = _mock_session_ctx()
            mock_session.return_value = mock_ctx
            db = mock_ctx.__enter__.return_value
            db.execute.return_value = _execute_result([])

            result = notify_breaking_issues(hours=2)

        assert result == 0

    def test_대표기사_없으면_알림없이_처리완료로_마킹(self):
        issue = MagicMock()
        issue.representative_article_id = None
        issue.breaking_notified_at = None

        with patch("app.db.notifier.get_session") as mock_session:
            mock_ctx = _mock_session_ctx()
            mock_session.return_value = mock_ctx
            db = mock_ctx.__enter__.return_value
            db.execute.return_value = _execute_result([issue])

            result = notify_breaking_issues(hours=2)

        assert result == 0
        assert issue.breaking_notified_at is not None

    def test_카테고리_없으면_알림없이_처리완료로_마킹(self):
        issue = MagicMock()
        issue.representative_article_id = uuid.uuid4()
        issue.category_id = uuid.uuid4()
        issue.breaking_notified_at = None

        with patch("app.db.notifier.get_session") as mock_session:
            mock_ctx = _mock_session_ctx()
            mock_session.return_value = mock_ctx
            db = mock_ctx.__enter__.return_value
            db.execute.return_value = _execute_result([issue])
            db.get.return_value = None  # Category 조회 결과 없음

            result = notify_breaking_issues(hours=2)

        assert result == 0
        assert issue.breaking_notified_at is not None

    def test_매칭_구독자에게_알림_생성_및_이메일_발송_시도(self):
        issue = MagicMock()
        issue.id = uuid.uuid4()
        issue.representative_article_id = uuid.uuid4()
        issue.category_id = uuid.uuid4()
        issue.title = "테스트 속보"
        issue.breaking_notified_at = None

        category = MagicMock()
        category.slug = "economy"

        sub = MagicMock()
        sub.user_id = uuid.uuid4()
        sub.id = uuid.uuid4()

        user = MagicMock()
        user.email = "test@example.com"

        def get_side_effect(model, _id):
            if model is Category:
                return category
            if model is User:
                return user
            return None

        with patch("app.db.notifier.get_session") as mock_session, \
             patch("app.db.notifier._send_breaking_email") as mock_send_email:
            mock_ctx = _mock_session_ctx()
            mock_session.return_value = mock_ctx
            db = mock_ctx.__enter__.return_value
            db.execute.side_effect = [_execute_result([issue]), _execute_result([sub])]
            db.get.side_effect = get_side_effect

            result = notify_breaking_issues(hours=2)

        assert result == 1
        assert issue.breaking_notified_at is not None
        mock_send_email.assert_called_once_with(
            to_email="test@example.com", issue_title="테스트 속보",
            issue_id=issue.id, category_value="economy",
        )

    def test_동일_사용자_중복구독이어도_알림은_한번만(self):
        issue = MagicMock()
        issue.id = uuid.uuid4()
        issue.representative_article_id = uuid.uuid4()
        issue.category_id = uuid.uuid4()
        issue.title = "테스트 속보"
        issue.breaking_notified_at = None

        category = MagicMock()
        category.slug = "economy"

        same_user_id = uuid.uuid4()
        sub1 = MagicMock(user_id=same_user_id, id=uuid.uuid4())
        sub2 = MagicMock(user_id=same_user_id, id=uuid.uuid4())

        user = MagicMock()
        user.email = "test@example.com"

        def get_side_effect(model, _id):
            if model is Category:
                return category
            if model is User:
                return user
            return None

        with patch("app.db.notifier.get_session") as mock_session, \
             patch("app.db.notifier._send_breaking_email"):
            mock_ctx = _mock_session_ctx()
            mock_session.return_value = mock_ctx
            db = mock_ctx.__enter__.return_value
            db.execute.side_effect = [_execute_result([issue]), _execute_result([sub1, sub2])]
            db.get.side_effect = get_side_effect

            result = notify_breaking_issues(hours=2)

        assert result == 1

    def test_이메일_없는_사용자는_스킵(self):
        issue = MagicMock()
        issue.id = uuid.uuid4()
        issue.representative_article_id = uuid.uuid4()
        issue.category_id = uuid.uuid4()
        issue.breaking_notified_at = None

        category = MagicMock()
        category.slug = "economy"

        sub = MagicMock(user_id=uuid.uuid4(), id=uuid.uuid4())
        user = MagicMock()
        user.email = None

        def get_side_effect(model, _id):
            if model is Category:
                return category
            if model is User:
                return user
            return None

        with patch("app.db.notifier.get_session") as mock_session, \
             patch("app.db.notifier._send_breaking_email") as mock_send_email:
            mock_ctx = _mock_session_ctx()
            mock_session.return_value = mock_ctx
            db = mock_ctx.__enter__.return_value
            db.execute.side_effect = [_execute_result([issue]), _execute_result([sub])]
            db.get.side_effect = get_side_effect

            result = notify_breaking_issues(hours=2)

        assert result == 0
        mock_send_email.assert_not_called()


class TestSendBreakingEmail:

    def test_SMTP_자격증명_없으면_발송_스킵(self):
        with patch("app.db.notifier._SMTP_USER", ""), \
             patch("app.db.notifier._SMTP_PASS", ""), \
             patch("app.db.notifier.smtplib.SMTP") as mock_smtp:
            _send_breaking_email("test@example.com", "제목", uuid.uuid4(), "economy")

        mock_smtp.assert_not_called()

    def test_발송_실패해도_예외를_전파하지_않는다(self):
        with patch("app.db.notifier._SMTP_USER", "user"), \
             patch("app.db.notifier._SMTP_PASS", "pass"), \
             patch("app.db.notifier.smtplib.SMTP", side_effect=Exception("연결 실패")):
            _send_breaking_email("test@example.com", "제목", uuid.uuid4(), "economy")

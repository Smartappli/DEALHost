from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase


class IamSecurityTests(APITestCase):
    def test_iam_api_rejects_anonymous_requests(self) -> None:
        response = self.client.get(reverse("iam-users-list"))

        self.assertIn(response.status_code, {401, 403})

    def test_iam_api_allows_superuser_requests(self) -> None:
        user = get_user_model().objects.create_user(
            username="admin",
            password="secret",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user)

        response = self.client.get(reverse("iam-users-list"))

        self.assertEqual(response.status_code, 200)

    def test_iam_api_rejects_non_superuser_staff(self) -> None:
        user = get_user_model().objects.create_user(
            username="staff",
            password="secret",
            is_staff=True,
            is_superuser=False,
        )
        self.client.force_authenticate(user)

        response = self.client.get(reverse("iam-users-list"))

        self.assertEqual(response.status_code, 403)

    def test_iam_api_allows_admin_bearer_token(self) -> None:
        response = self.client.get(
            reverse("iam-users-list"),
            HTTP_AUTHORIZATION="Bearer test-admin-token",
        )

        self.assertEqual(response.status_code, 200)

    def test_iam_api_rejects_readonly_bearer_token(self) -> None:
        response = self.client.get(
            reverse("iam-users-list"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 403)

    def test_iam_manage_requires_login(self) -> None:
        response = self.client.get(reverse("iam-management"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_iam_manage_rejects_non_superuser_staff(self) -> None:
        user = get_user_model().objects.create_user(
            username="staff",
            password="secret",
            is_staff=True,
            is_superuser=False,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("iam-management"))

        self.assertEqual(response.status_code, 403)

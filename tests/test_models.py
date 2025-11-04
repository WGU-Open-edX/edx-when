#!/usr/bin/env python
"""
Tests for the `edx-when` models module.
"""

from datetime import datetime, timedelta

import ddt
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey, UsageKey

from edx_when.models import ContentDate, DatePolicy, MissingScheduleError, UserDate
from tests.test_models_app.models import DummySchedule

User = get_user_model()


@ddt.ddt
class TestDatePolicy(TestCase):
    """
    Tests of the DatePolicy model.
    """

    @ddt.data(
        (None, None, None, None),
        (datetime(2020, 1, 1), None, None, datetime(2020, 1, 1)),
        (datetime(2020, 1, 1), None,
            DummySchedule(created=datetime(2020, 3, 1), start_date=datetime(2020, 3, 1)), datetime(2020, 1, 1)),
        (None, timedelta(days=1),
            DummySchedule(created=datetime(2020, 1, 1), start_date=datetime(2020, 1, 1)), datetime(2020, 1, 2)),
        (datetime(2020, 3, 1), timedelta(days=1),
            DummySchedule(created=datetime(2020, 1, 1), start_date=datetime(2020, 1, 1)), datetime(2020, 1, 2)),
    )
    @ddt.unpack
    def test_actual_date(self, abs_date, rel_date, schedule, expected):
        policy = DatePolicy(abs_date=abs_date, rel_date=rel_date)
        assert policy.actual_date(schedule) == expected

    @ddt.data(
        (None, timedelta(days=1), None),
        (datetime(2020, 1, 1), timedelta(days=1), None),
    )
    @ddt.unpack
    def test_actual_date_failure(self, abs_date, rel_date, schedule):
        policy = DatePolicy(abs_date=abs_date, rel_date=rel_date)
        with self.assertRaises(MissingScheduleError):
            policy.actual_date(schedule)

    def test_actual_date_schedule_after_end(self):
        # This only applies for relative dates so we are not testing abs date.
        policy = DatePolicy(rel_date=timedelta(days=1))
        schedule = DummySchedule(created=datetime(2020, 4, 1), start_date=datetime(2020, 4, 1))
        self.assertIsNone(policy.actual_date(schedule, end_datetime=datetime(2020, 1, 1)))

    def test_actual_date_schedule_after_cutoff(self):
        # This only applies for relative dates so we are not testing abs date.
        day = timedelta(days=1)
        policy = DatePolicy(rel_date=day)
        schedule = DummySchedule(created=datetime(2020, 4, 1), start_date=datetime(2020, 4, 1))
        self.assertIsNone(policy.actual_date(schedule, cutoff_datetime=schedule.created - day))
        self.assertIsNotNone(policy.actual_date(schedule, cutoff_datetime=schedule.created + day))

    def test_mixed_dates(self):
        with self.assertRaises(ValidationError):
            DatePolicy(abs_date=datetime(2020, 1, 1), rel_date=timedelta(days=1)).full_clean()


class TestUserDateModel(TestCase):
    """Tests for the UserDate model."""

    def setUp(self):
        """Set up a user and content date for the tests."""
        self.user = User.objects.create(username="test_user")
        self.course_key = CourseKey.from_string('course-v1:TestX+Test+2025')
        self.block_key = UsageKey.from_string('block-v1:TestX+Test+2025+type@sequential+block@test')
        self.course_block_key = UsageKey.from_string('block-v1:TestX+Test+2025+type@course+block@course')
        self.policy = DatePolicy.objects.create(abs_date=datetime(2025, 1, 15, 10, 0, 0))
        self.content_date = ContentDate.objects.create(
            course_id=self.course_key,
            location=self.block_key,
            field='due',
            active=True,
            policy=self.policy,
            block_type='sequential'
        )

    def test_learner_has_access_when_not_gated(self):
        """learner_has_access should be True when is_content_gated is False."""
        user_date = UserDate.objects.create(
            user=self.user,
            content_date=self.content_date,
            is_content_gated=False,
        )
        assert user_date.learner_has_access is True

    def test_learner_has_access_when_gated(self):
        """learner_has_access should be False when is_content_gated is True."""
        user_date = UserDate.objects.create(
            user=self.user,
            content_date=self.content_date,
            is_content_gated=True,
        )
        assert user_date.learner_has_access is False

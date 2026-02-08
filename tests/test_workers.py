"""
Unit tests for app.workers – scheduler and job functions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.scheduler import get_scheduler, start_scheduler, stop_scheduler


class TestScheduler:
    """Tests for scheduler module."""

    def test_get_scheduler_returns_singleton(self):
        """get_scheduler returns the same instance."""
        with patch("app.workers.scheduler._scheduler", None):
            s1 = get_scheduler()
            s2 = get_scheduler()
            assert s1 is s2

    @pytest.mark.asyncio
    async def test_start_scheduler_adds_jobs(self):
        """start_scheduler adds domain and SSL jobs."""
        mock_scheduler = MagicMock()
        with patch("app.workers.scheduler.get_scheduler", return_value=mock_scheduler):
            with patch("app.workers.scheduler.get_settings") as mock_settings:
                mock_settings.return_value.is_development = True
                await start_scheduler()
        assert mock_scheduler.add_job.call_count >= 2
        mock_scheduler.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_scheduler_adds_production_jobs(self):
        """start_scheduler adds rewards/payouts when not in dev."""
        mock_scheduler = MagicMock()
        with patch("app.workers.scheduler.get_scheduler", return_value=mock_scheduler):
            with patch("app.workers.scheduler.get_settings") as mock_settings:
                mock_settings.return_value.is_development = False
                await start_scheduler()
        assert mock_scheduler.add_job.call_count >= 5

    @pytest.mark.asyncio
    async def test_stop_scheduler_shuts_down(self):
        """stop_scheduler shuts down when running."""
        mock_scheduler = MagicMock()
        mock_scheduler.running = True
        with patch("app.workers.scheduler.get_scheduler", return_value=mock_scheduler):
            await stop_scheduler()
        mock_scheduler.shutdown.assert_called_once_with(wait=True)

    @pytest.mark.asyncio
    async def test_stop_scheduler_skips_when_not_running(self):
        """stop_scheduler does not shutdown when not running."""
        mock_scheduler = MagicMock()
        mock_scheduler.running = False
        with patch("app.workers.scheduler.get_scheduler", return_value=mock_scheduler):
            await stop_scheduler()
        mock_scheduler.shutdown.assert_not_called()


class TestDomainProcessorJob:
    """Tests for domain_processor job."""

    @pytest.mark.asyncio
    async def test_process_domains_job_calls_oracle(self):
        """process_domains_job calls oracle process_domains."""
        try:
            import oracle.domain_processor as dp_mod
        except ImportError:
            pytest.skip("oracle.domain_processor not available")
        with patch.object(dp_mod, "process_domains") as mock_process:
            from app.workers.domain_processor import process_domains_job
            await process_domains_job()
        mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_domains_job_handles_exception(self):
        """process_domains_job logs and re-raises on exception."""
        try:
            import oracle.domain_processor as dp_mod
        except ImportError:
            pytest.skip("oracle.domain_processor not available")
        with patch.object(dp_mod, "process_domains", side_effect=RuntimeError("oracle down")):
            from app.workers.domain_processor import process_domains_job
            with pytest.raises(RuntimeError, match="oracle down"):
                await process_domains_job()


class TestSslRenewalJob:
    """Tests for ssl_renewal job."""

    @pytest.mark.asyncio
    async def test_renew_ssl_skips_in_dev(self):
        """renew_ssl_certificates_job skips in development."""
        from app.workers.ssl_renewal import renew_ssl_certificates_job

        with patch("app.workers.ssl_renewal.get_settings") as mock_settings:
            mock_settings.return_value.is_development = True
            await renew_ssl_certificates_job()
        # No exception, returns early

    @pytest.mark.asyncio
    async def test_renew_ssl_runs_in_production(self):
        """renew_ssl_certificates_job runs SSLCertificateRenewer in production."""
        mock_renewer_class = MagicMock()
        fake_cert_mod = MagicMock()
        fake_cert_mod.SSLCertificateRenewer = mock_renewer_class
        import sys
        orig_ssl = sys.modules.get("scripts.ssl")
        orig_cert = sys.modules.get("scripts.ssl.renew_certificates")
        try:
            sys.modules["scripts.ssl.renew_certificates"] = fake_cert_mod
            if "scripts.ssl" not in sys.modules:
                sys.modules["scripts.ssl"] = MagicMock()
            with patch("app.workers.ssl_renewal.get_settings") as mock_settings:
                mock_settings.return_value.is_development = False
                from app.workers.ssl_renewal import renew_ssl_certificates_job
                await renew_ssl_certificates_job()
            mock_renewer_class.assert_called_once_with(use_staging=False, days_before_expiry=30)
            mock_renewer_class.return_value.run.assert_called_once()
        finally:
            if orig_cert is not None:
                sys.modules["scripts.ssl.renew_certificates"] = orig_cert
            elif "scripts.ssl.renew_certificates" in sys.modules:
                del sys.modules["scripts.ssl.renew_certificates"]
            if orig_ssl is not None:
                sys.modules["scripts.ssl"] = orig_ssl


class TestHourlyRewardsJob:
    """Tests for hourly_rewards job."""

    @pytest.mark.asyncio
    async def test_hourly_rewards_skips_in_dev(self):
        """process_hourly_rewards_job skips in development."""
        from app.workers.hourly_rewards import process_hourly_rewards_job

        with patch("app.workers.hourly_rewards.get_settings") as mock_settings:
            mock_settings.return_value.is_development = True
            await process_hourly_rewards_job()


class TestPayoutSchedulerJob:
    """Tests for payout_scheduler job."""

    @pytest.mark.asyncio
    async def test_payouts_skips_in_dev(self):
        """process_payouts_job skips in development."""
        from app.workers.payout_scheduler import process_payouts_job

        with patch("app.workers.payout_scheduler.get_settings") as mock_settings:
            mock_settings.return_value.is_development = True
            await process_payouts_job()

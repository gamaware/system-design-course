Rails.application.configure do
  # Settings specified here will take precedence over those in config/application.rb.

  # The test environment is used exclusively to run your application's
  # test suite. You never need to work with it otherwise.
  config.enable_reloading = false

  # Do not eager load code on boot. This avoids loading your whole application
  # just for the purpose of running a single test.
  config.eager_load = false

  # Configure static file server for tests with Cache-Control for performance.
  config.public_file_server.enabled = true
  config.public_file_server.headers = { 'Cache-Control' => 'public, max-age=3600' }

  # Show full error reports and disable caching.
  config.consider_all_requests_local       = true
  config.action_controller.perform_caching = false

  # Raise exceptions instead of rendering exception templates.
  config.action_dispatch.show_exceptions = :none

  # Disable request forgery protection in test environment.
  config.action_controller.allow_forgery_protection = false

  # Randomize the order test cases are executed.
  config.active_support.test_order = :random

  # Raises error for missing translations
  # config.i18n.raise_on_missing_translations = true
end

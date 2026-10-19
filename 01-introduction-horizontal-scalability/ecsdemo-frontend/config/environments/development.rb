Rails.application.configure do
  # Settings specified here will take precedence over those in config/application.rb.

  config.enable_reloading = false
  config.public_file_server.headers = { 'Cache-Control' => 'public, max-age=300' }

  # Eager load code on boot.
  config.eager_load = true

  # Show full error reports and enable caching.
  config.consider_all_requests_local       = true
  config.action_controller.perform_caching = true

  # Raises error for missing translations
  # config.i18n.raise_on_missing_translations = true
end

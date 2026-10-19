require_relative 'boot'

# Load only the frameworks this app uses (no database, mailers or jobs).
require 'rails'
require 'action_controller/railtie'
require 'action_view/railtie'

# Require the gems listed in Gemfile, including any gems
# you've limited to :test, :development, or :production.
Bundler.require(*Rails.groups)

module ExampleApp
  class Application < Rails::Application
    # Settings in config/environments/* take precedence over those specified here.
    # Application configuration should go into files in config/initializers
    # -- all .rb files in that directory are automatically loaded.

    # Set Time.zone default to the specified zone and make Active Record auto-convert to this zone.
    # Run "rake -D time" for a list of tasks for finding time zone names. Default is UTC.
    # config.time_zone = 'Central Time (US & Canada)'

    # The default locale is :en and all translations from config/locales/*.rb,yml are auto loaded.
    # config.i18n.load_path += Dir[Rails.root.join('my', 'locales', '*.{rb,yml}').to_s]
    # config.i18n.default_locale = :de

    # The app keeps no user data in cookies, so a per-boot random key is enough
    # when SECRET_KEY_BASE is not provided.
    config.secret_key_base = ENV.fetch('SECRET_KEY_BASE') { SecureRandom.hex(64) }

    # Since we run in a Docker container, always log to stdout
    config.logger = Logger.new(STDOUT)
    config.logger.level = Logger::ERROR
  end
end

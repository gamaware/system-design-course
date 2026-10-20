require "log"
require "http/server"

Log.setup(:debug)
log = Log.for("ecsdemo-crystal")

log.debug { "Created logger" }
log.info { "Program started" }
log.warn { "Nothing to do!" }

code_hash = File.read("code_hash.txt")
ip = ENV["IP"]
az = ENV["AZ"]
log.debug { "code_hash is: #{code_hash}" }
log.debug { "ip is: #{ip}" }
log.debug { "az is: #{az}" }

az_message = ENV["AZ"]

server = HTTP::Server.new(
  [
    HTTP::ErrorHandler.new,
    HTTP::LogHandler.new,
    HTTP::CompressHandler.new,
    ]) do |context|
      # the frontend sends the full URL ("GET http://host:3000/crystal"), so match on its path only
      path = URI.parse(context.request.resource).path
      if path == "/crystal" || path == "/crystal/"
        context.response.content_type = "text/plain"
        context.response.print "Crystal backend: Hello! from #{az_message} commit #{code_hash}"
      elsif path == "/crystal/api" || path == "/crystal/api/"
        context.response.content_type = "application/json"
        context.response.print %Q({"from":"Crystal backend", "message": "#{az_message}", "commit": "#{code_hash.chomp}"})
      elsif path == "/health"
        context.response.content_type = "text/plain"
        context.response.print "Healthy!"
      else
        context.response.status_code = 404
        context.response.headers["Content-Type"] = "text/plain"
        context.response.puts "Not Found"
      end
    end

puts "Listening on http://0.0.0.0:3000"
server.bind_tcp "0.0.0.0", 3000
server.listen

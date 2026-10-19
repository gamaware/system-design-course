# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/sdk:8.0.426-bookworm-slim AS build
WORKDIR /src
COPY CacheLab.csproj .
RUN dotnet restore
COPY . .
RUN dotnet publish -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/runtime:8.0.32-bookworm-slim
WORKDIR /app
COPY --from=build /app .
ENTRYPOINT ["dotnet", "CacheLab.dll"]

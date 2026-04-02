# syntax=docker/dockerfile:1

# --- Build stage ---
FROM maven:3.9-eclipse-temurin-21 AS build

WORKDIR /app

COPY pom.xml .
RUN mvn dependency:resolve

COPY src/ src/
RUN mvn package -DskipTests

# --- Runtime stage ---
FROM eclipse-temurin:21-jre

WORKDIR /app

COPY --from=build /app/target/cache-lab-1.0.jar app.jar

ENTRYPOINT ["java", "-jar", "app.jar"]

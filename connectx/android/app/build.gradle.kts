import java.util.Properties

plugins {
    id("com.android.application")
    // Add the Google services Gradle plugin
    id("com.google.gms.google-services")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val keyPropertiesFile = rootProject.file("key.properties")
val keyProperties = Properties()
if (keyPropertiesFile.exists()) {
    keyProperties.load(keyPropertiesFile.inputStream())
}

android {
    namespace = "com.fides.connectx"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
        isCoreLibraryDesugaringEnabled = true
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_21.toString()
    }

    signingConfigs {
        if (keyPropertiesFile.exists()) {
            create("release") {
                val alias = keyProperties.getProperty("keyAlias")
                    ?: throw GradleException("key.properties is missing required property 'keyAlias'")
                val keyPass = keyProperties.getProperty("keyPassword")
                    ?: throw GradleException("key.properties is missing required property 'keyPassword'")
                val storeFilePath = keyProperties.getProperty("storeFile")
                    ?: throw GradleException("key.properties is missing required property 'storeFile'")
                val storePass = keyProperties.getProperty("storePassword")
                    ?: throw GradleException("key.properties is missing required property 'storePassword'")
                keyAlias = alias
                keyPassword = keyPass
                storeFile = file(storeFilePath)
                storePassword = storePass
            }
        }
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.fides.connectx"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        multiDexEnabled = true
    }

    buildTypes {
        release {
            signingConfig = if (keyPropertiesFile.exists()) {
                signingConfigs.getByName("release")
            } else {
                signingConfigs.getByName("debug")
            }
        }
    }

    flavorDimensions += "mode"
    productFlavors {
        create("full") {
            dimension = "mode"
        }
        create("lite") {
            dimension = "mode"
        }
    }
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
    // Import the Firebase BoM
    implementation(platform("com.google.firebase:firebase-bom:34.9.0"))
    // Firebase Auth (version managed by BoM)
    implementation("com.google.firebase:firebase-auth")
}

flutter {
    source = "../.."
}

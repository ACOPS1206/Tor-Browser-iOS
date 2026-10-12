platform :ios, '17.4'
project 'Reynard.xcodeproj'
install! 'cocoapods', :warn_for_unused_master_specs_repo => false
use_frameworks! :linkage => :static

target 'Reynard' do
  pod 'Tor/CTor', :git => 'https://github.com/iCepa/Tor.framework.git', :commit => '51cc492a817bbbc8a647b493d7dde2c0b765ae41'
end

post_install do |installer|
  # Scope CocoaPods linkage to the host app; Gecko/helper must not statically
  # link their own copies of Tor's Objective-C classes and crypto libraries.
  installer.aggregate_targets.each do |aggregate|
    project = aggregate.user_project
    aggregate.user_targets.select { |target| target.name == 'Reynard' }.each do |target|
      target.build_configurations.each do |config|
        relative = "Configuration/Tor.#{config.name}.xcconfig"
        filename = File.join(project.path.dirname.to_s, relative)
        pods = "../Pods/Target Support Files/Pods-Reynard/Pods-Reynard.#{config.name.downcase}.xcconfig"
        File.write(filename, <<~CONFIG)
          #include "Reynard.xcconfig"
          #include "#{pods}"
          HEADER_SEARCH_PATHS = $(inherited) $(GECKO_DIST)/include $(GECKO_DIST)/include/GeckoView $(SRCROOT)/GeckoView "$(PODS_ROOT)/Headers/Public" "$(PODS_CONFIGURATION_BUILD_DIR)/Tor/Tor.framework/Headers"
          LIBRARY_SEARCH_PATHS = $(inherited) $(GECKO_DIST)/bin
          FRAMEWORK_SEARCH_PATHS = $(inherited) $(BUILT_PRODUCTS_DIR) "$(PODS_CONFIGURATION_BUILD_DIR)/Tor" "$(PODS_XCFRAMEWORKS_BUILD_DIR)/Tor"
        CONFIG
        config.base_configuration_reference = project.main_group.new_file(relative)
      end
    end
    project.save
  end
  # TORThread builds argv with a trailing NULL; reserve space for that sentinel.
  thread = File.join(installer.sandbox.root.to_s, 'Tor/Tor/Classes/CTor/TORThread.m')
  if File.exist?(thread)
    source = File.read(thread)
    File.write(thread, source.sub('char *argv[argc];', 'char *argv[argc + 1];'))
  end
  installer.pods_project.targets.each do |target|
    target.build_configurations.each do |config|
      config.build_settings['IPHONEOS_DEPLOYMENT_TARGET'] = '17.4'
      config.build_settings['CODE_SIGNING_ALLOWED'] = 'NO'
    end
  end
end

platform :ios, '17.4'
project 'Reynard.xcodeproj'
install! 'cocoapods', :warn_for_unused_master_specs_repo => false
use_frameworks! :linkage => :static

target 'Reynard' do
  pod 'Tor/CTor', :git => 'https://github.com/iCepa/Tor.framework.git', :commit => '51cc492a817bbbc8a647b493d7dde2c0b765ae41'
end

post_install do |installer|
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

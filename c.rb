#!/usr/bin/env ruby
# frozen_string_literal: true

# SPDX-License-Identifier: Apache-2.0

# rubocop:disable Lint/MissingCopEnableDirective

# rubocop:disable Layout/EmptyLineAfterGuardClause
# rubocop:disable Layout/HeredocIndentation
# rubocop:disable Layout/LineLength
# rubocop:disable Style/StringLiteralsInInterpolation
# rubocop:disable Style/TrailingCommaInArguments
# rubocop:disable Style/TrailingCommaInArrayLiteral
# rubocop:disable Style/TrailingCommaInHashLiteral

# mini CLIs

require "date"
require "json"
require "logger"
require "open3"
require "optparse"
require "stringio"

Logger_ = Logger.new($stderr, level: Logger::WARN)

def logger
  Logger_
end

class MyError < StandardError; end

# ------------------------------------------------------------------------------
# lib

# @param [Boolean] expr
def assert(expr)
  return if expr
  locs = caller_locations
  msg = "assertion failed: #{locs[0]}: #{File.read(locs[0].absolute_path).lines[locs[0].lineno - 1].strip} [-> #{expr}]"
  debugger_try(2) do
    logger.error(msg)
    logger.error("going into debugger")
  end
  raise msg
end

# @param [Integer] frame
# @param [Proc] log_cb
# @return [Boolean]
def debugger_try(frame, &log_cb)
  begin
    require "debug"
  rescue LoadError
    return false
  end
  return false unless respond_to?(:debugger)
  log_cb.call
  $nop = ->(*_) {}
  debugger(pre: "'=' * 80;;frame 2;;l") # rubocop:disable Lint/Debugger
  debugger(pre: "\"-\" * 80  $nop[\"#{"-" * 80}\"];;frame #{frame};;l") # rubocop:disable Lint/Debugger
  # debugger(do: "")
  # debugger(pre: "l;;frame 1;;l", do: nil)
  true
end

# @param [String] str
# @param [Integer] width
# @return [String]
def str_snip(str, width = 100)
  # str = str.gsub("\n", "␊").gsub("\r", "␍")
  str = str.gsub("\n", "⏎").gsub("\r", "␍")
  return str if width == -1
  raise ArgumentError, "width must be -1 or greater than 3" if width <= 3
  return str if str.length <= width
  width1 = ((width - "...".length + 1) / 2)
  width2 = ((width - "...".length) / 2)
  "#{str[...width1]}...#{str[(str.length - width2)..]}"
end

def _str_snip_test # rubocop:disable Metrics
  str_snip("123456789", 3) # width must be -1 or greater than 3 (ArgumentError)
  raise unless str_snip("123456789", 4) == "1..."
  raise unless str_snip("123456789", 5) == "1...9"
  raise unless str_snip("123456789", 6) == "12...9"
  raise unless str_snip("123456789", 7) == "12...89"
  raise unless str_snip("123456789", 8) == "123...89"
  raise unless str_snip("123456789", 9) == "123456789"
  raise unless str_snip("123456789", -1) == "123456789"
  raise unless str_snip("1\r\n3\r\n5\n7\n9", 8) == "1␍⏎...⏎9"
end

# ------------------------------------------------------------------------------
# commands

# @type [Hash{String => Proc}]
$commands = {}
# @type [Hash{String => OptionParser}]
$opt_parsers = {}

Opt_parser_only_help = OptionParser.new do |parser| # rubocop:disable
  parser.on("-h", "--help", "print this help") do
    puts(parser.help)
    exit(0)
  end
end

# @param [String] name
# @param [OptionParser, nil] opt_parser
def command(name, opt_parser = nil, &block)
  $commands[name] = block
  $opt_parsers[name] = opt_parser.nil? ? Opt_parser_only_help : opt_parser
end

# @param [String] arg_spec
# @param [String] usage
# @return [Array<String>]
def command_arg_parse(arg_spec, usage)
  # TODO: show usage

  # ARG1 [ARG2] [ARGF]
  #     |-> in_optional_specs
  ret = []
  specs = arg_spec.split
  in_optional_specs = false
  specs.each_with_index do |spec, i|
    case spec
    when /^\[(\w+)\]$/
      return ret if ARGV.empty? # rubocop:disable Lint/NonLocalExitFromIterator
      in_optional_specs = true
      if Regexp.last_match[1] == "ARGF"
        assert(i == specs.length - 1)
        return ret if ARGV.length in 0..1 # rubocop:disable Lint/NonLocalExitFromIterator
        raise OptionParser::InvalidArgument, "excess argument(s): #{ARGV[1..]}"
      end
      ret.push(ARGV.shift)
    when /^(\w+)$/
      assert(Regexp.last_match[1] != "ARGF")
      assert(!in_optional_specs)
      raise OptionParser::MissingArgument, "#{spec}" if ARGV.empty?
      ret.push(ARGV.shift)
    else
      raise "invalid spec: #{spec}"
    end
  end
  raise OptionParser::InvalidArgument, "excess argument(s): #{ARGV}" unless ARGV.empty?
  ret
end

=begin # rubocop:disable Style/BlockComments
ARG1 [ARG2]        : [[]] missing argument: ARG1
ARG1 [ARG2] [ARGF] : [[]] missing argument: ARG1
ARG1 [ARG2]        : [["arg1"]] OK ARG1:"arg1" ARG2:nil ARGV:[]
ARG1 [ARG2] [ARGF] : [["arg1"]] OK ARG1:"arg1" ARG2:nil ARGV:[]
ARG1 [ARG2]        : [["arg1", "arg2"]] OK ARG1:"arg1" ARG2:"arg2" ARGV:[]
ARG1 [ARG2] [ARGF] : [["arg1", "arg2"]] OK ARG1:"arg1" ARG2:"arg2" ARGV:[]
ARG1 [ARG2]        : [["arg1", "arg2", "arg3"]] invalid argument: excess argument(s): ["arg3"]
ARG1 [ARG2] [ARGF] : [["arg1", "arg2", "arg3"]] OK ARG1:"arg1" ARG2:"arg2" ARGV:["arg3"]
ARG1 [ARG2]        : [["arg1", "arg2", "arg3", "arg4"]] invalid argument: excess argument(s): ["arg3", "arg4"]
ARG1 [ARG2] [ARGF] : [["arg1", "arg2", "arg3", "arg4"]] invalid argument: excess argument(s): ["arg4"]
ARG1 [ARG2]        : [["arg1", "arg2", "arg3", "arg4", "arg5"]] invalid argument: excess argument(s): ["arg3", "arg4", "arg5"]
ARG1 [ARG2] [ARGF] : [["arg1", "arg2", "arg3", "arg4", "arg5"]] invalid argument: excess argument(s): ["arg4", "arg5"]
=end
def _test_command_arg_parse
  argv_orig = ARGV

  [
    %w[],
    %w[arg1],
    %w[arg1 arg2],
    %w[arg1 arg2 arg3],
    %w[arg1 arg2 arg3 arg4],
    %w[arg1 arg2 arg3 arg4 arg5],
  ].each do |args|
    ARGV.replace(args)
    begin
      arg1, arg2 = command_arg_parse("ARG1 [ARG2]", "usage")
    rescue OptParse::ParseError => e
      puts("ARG1 [ARG2]        : [#{args}] #{e}")
    else
      puts("ARG1 [ARG2]        : [#{args}] OK ARG1:#{arg1.inspect} ARG2:#{arg2.inspect} ARGV:#{ARGV.inspect}")
    end

    ARGV.replace(args)
    begin
      arg1, arg2 = command_arg_parse("ARG1 [ARG2] [ARGF]", "usage")
    rescue OptParse::ParseError => e
      puts("ARG1 [ARG2] [ARGF] : [#{args}] #{e}")
    else
      puts("ARG1 [ARG2] [ARGF] : [#{args}] OK ARG1:#{arg1.inspect} ARG2:#{arg2.inspect} ARGV:#{ARGV.inspect}")
    end
  end

  ARGV.replace(argv_orig)
end

# _test_command_arg_parse

# ------------------------------------------------------------------------------
# command - 0sandbox @pub

command("0sandbox") do |opts_g|
  # use test stdin for RubyMine local debug
  #   RubyMine local debug:                              DEBUGGER_HOST: 0.0.0.0 RM_INFO=RM-222.3739.56
  #   rdebug-ide --host 0.0.0.0 + RubyMine remote debug: DEBUGGER_HOST: 0.0.0.0 (RM_INFO not set)
  #     rdebug-ide では Interrupt がハンドリングされてるっぽいくて ^C で終了できない [1]; pkill rdebug-ide で終了する; [1]: test: begin; sleep(100); rescue Exception => e; p(e); end; exit(0)
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    $stdin = StringIO.new(<<TEST_INPUT)
TEST_INPUT
  end

  tmp = command_arg_parse("[ARGF]", "usage: 0sandbox < FILE")
  $stdout.sync = true # without this: "COMMAND | cat" buffers the stdout
  # echo -en 'a \nb \r\nc ' | ruby ... -> line: "a \n" "b \r\n" "c " -rstrip-> "a" "b" "c"
  begin
    while (line = ARGF.gets&.rstrip)
      logger.info(line)
    end
  rescue Interrupt
    # Ignored
  end
  0
end

# ------------------------------------------------------------------------------
# command - c-decrement-line @pub

command("c-decrement-line") do |opts_g|
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    ARGV[0] = "yacc/tes.l"
    $stdin = StringIO.new(<<TEST_INPUT)
A
#line 34 "yacc/tes.l"
#line 35 "yacc/tes.l"
z
TEST_INPUT
  end

  FILE_L = command_arg_parse("FILE_L", "usage: c-decrement-line FILE_L < FILE_C") # rubocop:disable Lint/ConstantDefinitionInBlock
  print(ARGF.read.gsub(/^#line (\d+) ("#{FILE_L}")$/) { "#line #{$1.to_i - 1} #{$2}" })
  0
end

# ------------------------------------------------------------------------------
# command - cdb-files @pub

command("cdb-files") do |opts_g|
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    $stdin = StringIO.new(<<TEST_INPUT)
[
  {"directory":"dir1", "file":"file1"},
  {"directory":"dir2", "file":"file2"}
]
TEST_INPUT
  end

  command_arg_parse("[ARGF]", "usage: cdb-files < FILE")
  json = JSON.parse(ARGF.read)
  out = json.map do |entry|
    File.join(entry["directory"], entry["file"])
  end.join(" ")
  puts(out)
  0
end

# ------------------------------------------------------------------------------
# command - copy-replace @pub

command("copy-replace") do |opts_g|
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    $stdin = StringIO.new(<<TEST_INPUT)
TEST_INPUT
  end

  FROM, TO = command_arg_parse("FROM TO [ARGF]", "usage: copy-replace FROM TO < FILE")
  $stdout.sync = true # without this: "COMMAND | cat" buffers the stdout

  begin
    while (line = ARGF.gets&.rstrip)
      puts(line)
      puts(line.gsub(FROM, TO)) if line.include?(FROM)
    end
  rescue Interrupt
    # Ignored
  end
  0
end

# ------------------------------------------------------------------------------
# command - date-list @pub

command("date-list") do |opts_g|
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    $stdin = StringIO.new(<<TEST_INPUT)
TEST_INPUT
  end

  # https://docs.ruby-lang.org/ja/latest/class/Date.html

  Date.new(1970, 1, 1)
  Date.new(year = 1970, mon = 1, mday = 1)
  Date.httpdate("Mon, 01 Jan -4712 00:00:00 GMT") # parse RFC 2616 https://www.rfc-editor.org/rfc/rfc2616#section-3.3
  Date._httpdate("Mon, 01 Jan -4712 00:00:00 GMT") # as hash
  Date.iso8601("-4712-01-01") # parse [[ISO:8601]]
  Date._iso8601("-4712-01-01") # as hash
  Date.today
  Date.strptime("-4712-01-01", "%F")
  Date._strptime("-4712-01-01", "%F")

  Date.today.next_day
  Date.today + 1 # same
  Date.today.succ # same
  Date.today.next # same
  Date.today.prev_day
  Date.today - 1 # same
  Date.today.prev_month
  Date.today << 1 # same
  Date.today.next_month
  Date.today >> 1 # same
  Date.today === Date.today # same date?
  Date.today == Date.today # TODO: === と違いあるか調べる

  Date.today.year
  Date.today.month
  Date.today.mday # month of day
  Date.today.day # same
  Date.today.yday # year of day 1-366

  Date.today.downto(Date.today.prev_month).to_a
  Date.today.step(Date.today.prev_month, -1).to_a # same
  Date.today.upto(Date.today.next_month).to_a
  Date.today.step(Date.today.next_month, 1).to_a # same

  Date.today.strftime("%F")
  Date.today.to_datetime # 00:00:00
  Date.today.wday # weekday 0-6

  command_arg_parse("", "usage: date-list")
  Date.today.downto(Date.today.prev_month) { |date| puts(date.strftime("%F %a")) }

  0
end

# ------------------------------------------------------------------------------
# command - dns-resolve-hosts @pub

command("dns-resolve-hosts") do |opts_g|
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    $stdin = StringIO.new(<<TEST_INPUT)
TEST_INPUT
  end

  command_arg_parse("[ARGF]", "usage: dns-resolve-hosts < FILE")
  $stdout.sync = true # without this: "COMMAND | cat" buffers the stdout
  begin
    txt = ARGF.read.scan(/^__RESOLVE_BEGIN__\r?\n([\s\S]*?)\r?\n__RESOLVE_END__$/)[0][0]
    hosts = txt.scan(/[-.\w]+/).filter { |host| /^\d+\.\d+\.\d+\.\d+$/.match(host).nil? }.uniq
    hosts.each do |host|
      txt = Open3.capture2("host #{host}")[0]
      txt.scan(/has address (.+)$/) { |matches| puts("#{matches[0]}\t#{host}") }
      txt.scan(/has IPv6 address (.+)$/) { |matches| puts("#{matches[0]}\t#{host}") }
    end
  rescue Interrupt
    # Ignored
  end
  0
end

# ------------------------------------------------------------------------------
# command - kill-fish @pub

command("kill-fish") do |opts_g|
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    $stdin = StringIO.new(<<TEST_INPUT)
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
wsh        20434  0.0  0.0 263396  9476 pts/3    S+    5月19   0:00 fish
wsh       888495  0.0  0.0 263576  9836 pts/1    S     5月21   0:00 fish
wsh      1179690  0.0  0.0 263580  9964 pts/2    S+    5月23   0:00 fish
wsh      1958229  0.2  0.0 329380 23876 pts/5    S+   17:09   0:05 fish
wsh      1974475 29.9  0.0 3540916 35384 pts/0   Sl   17:27   5:41 fish <- kill this
wsh      1983736  1.6  0.0 328792 22784 pts/4    S+   17:43   0:02 fish
TEST_INPUT
  end

  command_arg_parse("", "usage: kill-fish")
  ps = Open3.capture2("ps -Cfish u")
  columns = ps[0].split(/\r?\n/)[0].split(" ")
  raise unless columns[1] == "PID"
  raise unless columns[2] == "%CPU"
  ps[0].split(/\r?\n/)[1..].each do |line|
    values = line.split
    pid = values[1].to_i
    cpu = values[2].to_f
    next if cpu < 20
    puts("kill #{pid} (#{cpu}%, #{line})")
    system("kill #{pid}")
  end
  0
end

# ------------------------------------------------------------------------------
# command - negate-network @pub

# この複雑さはrubyでやるべきではなかった

# dummy type definition for IDEs
# @attr_reader [Boolean] _6
class OptsNegateNetwork < Struct; end

real_opts_class = Struct.new(
  :ipv6,
)

# @type [OptsNegateNetwork]
opts_negate_network = lambda do
  real_opts_class.new(
    ipv6: false,
  )
end[]

opt_parser = OptionParser.new do |parser| # rubocop:disable
  opts = opts_negate_network
  # rubocop:disable Style/Semicolon
  parser.on("-h", "--help", "print this help") { puts(parser.help); exit(0); }
  parser.on("-6", "--ipv6", "use IPv6") { |arg| opts.ipv6 = arg; }
  # rubocop:enable Style/Semicolon
end

command("negate-network", opt_parser) do |opts_g|
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    $stdin = StringIO.new(<<TEST_INPUT)
TEST_INPUT
  end

  opts = opts_negate_network
  MARKER = command_arg_parse("MARKER [ARGF]", "usage: negate-network [-6] MARKER < FILE") # rubocop:disable Lint/ConstantDefinitionInBlock
  $stdout.sync = true # without this: "COMMAND | cat" buffers the stdout

  require "ipaddr"

  af, addr_i_max = if opts.ipv6
                     [Socket::AF_INET6, IPAddr.new("::/0", Socket::AF_INET6).to_range.end.to_i]
                   else
                     [Socket::AF_INET, IPAddr.new("255.255.255.255", Socket::AF_INET).to_i]
                   end

  begin
    exclude_networks = []
    while (line = ARGF.gets&.rstrip)
      if af == Socket::AF_INET
        match_data = line.match(/^#{MARKER}\t([\d.]+\/\d+).*$/)
      else
        match_data = line.match(/^#{MARKER}\t([\h:]+\/\d+).*$/)
      end
      next if match_data.nil?
      exclude_networks.push(IPAddr.new(match_data[1], af))
    end
  rescue Interrupt
    # Ignored
  end

  pairs_exclude_begin_end = [[-Float::INFINITY, -1]]
  exclude_networks.sort.each_with_index do |ex_net, i|
    ex_begin = ex_net.to_i
    ex_end = ex_net.to_range.end.to_i
    if pairs_exclude_begin_end[-1][1].succ >= ex_begin
      # merge
      pairs_exclude_begin_end[-1][1] = ex_end
      next
    end
    pairs_exclude_begin_end.push([ex_begin, ex_end])
    next
  end
  if pairs_exclude_begin_end[-1][1] == addr_i_max
    pairs_exclude_begin_end[-1][1] = Float::INFINITY
  else
    pairs_exclude_begin_end.push([addr_i_max.succ, Float::INFINITY])
  end
  raise "BUG" if pairs_exclude_begin_end != pairs_exclude_begin_end.sort

  # range_to_nets[0, 4294967294, Socket::AF_INET] # => [0.0.0.0/0]
  range_to_nets = lambda do |net_begin, net_end, af|
    raise "BUG" if net_end < net_begin
    nets = []
    loop do
      0.upto(af == Socket::AF_INET ? 32 : 128) do |mask|
        net = IPAddr.new(net_begin, af).mask(mask)
        next if net.to_i < net_begin # too large mask
        raise "BUG" if net.to_i != net_begin
        next if net.to_range.end.to_i > net_end # too large mask
        nets.push(net)
        return nets if net.to_range.end.to_i == net_end
        net_begin = net.to_range.end.to_i.succ
        raise "BUG" if net_begin > net_end
        break
      end
    end
    raise "NOTREACHED"
  end

  nets = []
  pairs_exclude_begin_end.each_with_index do |(ex_begin, ex_end), i|
    next if i.zero?
    include_begin = pairs_exclude_begin_end[i - 1][1].succ
    include_end = ex_begin.to_i.pred
    nets += range_to_nets[include_begin, include_end, af]
  end
  nets.each do |net|
    puts("#{net}/#{net.prefix} | #{net.to_range.begin} - #{net.to_range.end}")
  end

  0
end

# ------------------------------------------------------------------------------
# command - nl - terminate with new line @pub

# echo -n 'nl me!' | ruby -e 'puts(ARGF.read.sub(/(?<!\n)\z/, "\n"))'
# echo    'nop me' | ruby -e 'puts(ARGF.read.sub(/(?<!\n)\z/, "\n"))'

command("nl") do |opts_g|
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    $stdin = StringIO.new("nl me!")
    # $stdin = StringIO.new("nop me\n")
  end

  command_arg_parse("[ARGF]", "usage: nl < FILE")
  /(?<!\n)\z/.match?("nl me!") # true
  /(?<!\n)\z/.match?("nop me\n") # false
  puts(ARGF.read.sub(/(?<!\n)\z/, "\n"))
  0
end

# ------------------------------------------------------------------------------
# command - nl-trim @pub

# echo -en 'trim me!\n\n' | ruby -e 'print(ARGF.read.sub(/\n+\z/, ""))'
# echo -en 'trim me!\n'   | ruby -e 'print(ARGF.read.sub(/\n+\z/, ""))'
# echo -en 'nop me'       | ruby -e 'print(ARGF.read.sub(/\n+\z/, ""))'

command("nl-trim") do |opts_g|
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    $stdin = StringIO.new("trim me!\n\n")
    # $stdin = StringIO.new("trim me!\n")
    # $stdin = StringIO.new("nop me")
  end

  command_arg_parse("[ARGF]", "usage: nl-trim < FILE")
  /\n+\z/.match?("trim me!\n\n") # true
  /\n+\z/.match?("trim me!\n") # true
  /\n+\z/.match?("nop me") # false
  print(ARGF.read.sub(/\n+\z/, ""))
  0
end

# ------------------------------------------------------------------------------
# command - notify-fdinfo-find @pub

command("inotify-fdinfo-find") do |opts_g|
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    $stdin = StringIO.new(<<TEST_INPUT)
inotify wd:1 ino:394027a sdev:fd00001 mask:fc6 ignored_mask:0 fhandle-bytes:8 fhandle-type:1 f_handle:7a029403b8034d62
inotify wd:1 ino:394027a sdev:fd00001 mask:fc6 ignored_mask:0 fhandle-bytes:8 fhandle-type:1 f_handle:7a029403b8034d62
TEST_INPUT
  end

  command_arg_parse("[ARGF]", "usage: notify-fdinfo-find < FILE")
  # -inum 60031610 -or -inum 60031610
  out = ARGF.read.split(/\r?\n/).map do |line|
    "-inum #{/^inotify wd:\h+ ino:(\h+) .+$/.match(line)[1].to_i(16)}"
  end.join(" -or ")
  puts(out)
  0
end

# ------------------------------------------------------------------------------
# command - pandoc-json-remove-table-align @pub

command("pandoc-json-remove-table-align") do |opts_g|
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    $stdin = StringIO.new(<<TEST_INPUT)
aaa[42] [3.14] [3.14e-42] [42,3.14,3.14e-42]xxx
aaa[42] [3.14] [3.14e-42] [42,3.14,3.14e-42]xxx
-> []
should keep: "pandoc-api-version":[1,17,5,4]
TEST_INPUT
  end

  command_arg_parse("[ARGF]", "usage: pandoc-json-remove-table-align < FILE")
  # https://stackoverflow.com/questions/13340717/json-numbers-regular-expression
  number = /-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/
  puts(ARGF.read.sub("\"pandoc-api-version\":[", "\"pandoc-api-version\":[ ").gsub(/\[#{number}(,#{number})*\]/, "[]"))
  0
end

# ------------------------------------------------------------------------------
# command - systemd-analyze-dot-only-n @pub

command("systemd-analyze-dot-only-n") do |opts_g|
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    ARGV[0] = "3"
    $stdin = StringIO.new(<<TEST_INPUT)
digraph systemd {
	"blockdev@dev-loop25.target"->"shutdown.target" [color="red"];
	"fwupd-refresh.timer"->"sysinit.target" [color="green"];
	"fwupd-refresh.timer"->"time-sync.target" [color="green"];
}
TEST_INPUT
  end

  N = command_arg_parse("[ARGF]", "usage: systemd-analyze-dot-only-n N < FILE") # rubocop:disable Lint/ConstantDefinitionInBlock
  n = N.to_i(10)

  txt = ARGF.read
  pairs_unit_count = Hash.new(0)

  txt.scan(/^\t"(.+?)"->"(.+?)" \[color="\w+"\];$/) do |left, right|
    pairs_unit_count[left] += 1
    pairs_unit_count[right] += 1
  end

  n_units = pairs_unit_count.sort_by { |_unit, count| -count }.first(n).map { |unit, _count| unit }.to_set

  # n_units.add("postfix.service")
  # n_units.delete("shutdown.target")

  txt.split(/\r?\n/) do |line|
    unless line.start_with?("\t")
      puts(line)
      next
    end
    match_data = /^\t"(.+?)"->"(.+?)" \[color="\w+"\];$/.match(line)
    if match_data.nil?
      warn("unexpected line: #{line}")
      next
    end
    next unless n_units.include?(match_data[1]) && n_units.include?(match_data[2])
    puts(line)
  end

  0
end

# ------------------------------------------------------------------------------
# command - z-meta-publish-self @pub

=begin # rubocop:disable Style/BlockComments
c.rb -v z-meta-publish-self > ~/src/scraps/c.rb
delta ~/qrb/tesrb/c.rb ~/src/scraps/c.rb
=end

command("z-meta-publish-self") do |opts_g|
  if ENV.key?("DEBUGGER_HOST") && ENV.key?("RM_INFO")
    $stdin = StringIO.new(<<TEST_INPUT)
TEST_INPUT
  end

  command_arg_parse("", "usage: z-meta-publish-self")

  File.open(__FILE__) do |f|
    pub = true
    while (line = f.gets&.rstrip)
      case line
      when /^# command - [-\w]+ @pub$/
        logger.info("[public: #{pub} -> true] #{line}")
        pub = true
      when /^# command - [-\w]+$/
        logger.info("[public: #{pub} -> false] #{line}")
        pub = false
      else
        logger.debug(line)
      end
      next if line.match?(/[@]private/)
      next unless pub
      puts(line)
    end
  end

  0
end

# ------------------------------------------------------------------------------
# top command

Version = [0, 0, 0].freeze # rubocop:disable Naming/ConstantName
Release = "2023-03-05" # rubocop:disable Naming/ConstantName

# dummy type definition for IDEs
# @attr_reader [Boolean] quiet
# @attr_reader [Integer] verbose
class OptsGlobal < Struct; end

OptsGlobal_ = Struct.new(
  :quiet,
  :verbose,
)

# @type [OptsGlobal]
opts_g = lambda do
  OptsGlobal_.new(
    quiet: false,
    verbose: 0,
  )
end[]

opt_parser = OptionParser.new do |parser|
  # rubocop:disable Style/Semicolon
  parser.on("-h", "--help", "print this help") { puts(parser.help); exit(0); }
  parser.on("-q", "quiet mode") { |arg| raise OptionParser::ParseError, "-q and -v are mutually exclusive" if logger.level < Logger::WARN; logger.level = Logger::ERROR; opts_g.quiet = true }
  parser.on("-v", "print verbose output; -vv to show debug output") { |arg| raise OptionParser::ParseError, "-q and -v are mutually exclusive" if logger.level > Logger::WARN; logger.level = [Logger::DEBUG, logger.level - 1].max; opts_g.verbose += 1 }
  # rubocop:enable Style/Semicolon
end

# https://github.com/ruby/ruby/blob/v3_2_1/lib/optparse.rb#L1237
opt_parser.banner = <<EOS
Usage: #{opt_parser.program_name} [Global options] COMMAND [-h | --help] ...
  Global options:
EOS
# rubocop:enable Layout/HeredocIndentation

def opt_parser.help
  orig_help = super
  # rubocop:disable Layout/HeredocIndentation
  <<EOS
#{orig_help.rstrip}
  COMMANDs:
    #{$commands.keys.join(" | ")}
EOS
  # rubocop:enable Layout/HeredocIndentation
end

# ------------------------------------------------------------------------------
# main

# ARGV = %w[]                             # missing argument: COMMAND not specified
# ARGV = %w[-z]                           # invalid option: -z
# ARGV = %w[   xxx]                       # invalid argument: no such COMMAND: xxx
# ARGV = %w[-- xxx]                       # invalid argument: no such COMMAND: xxx
# ARGV = %w[-v    0sandbox    -z]         # invalid option: -z
# ARGV = %w[-v    0sandbox -- -z]         # /home/wsh/bin/c.rb:216:in `gets': No such file or directory @ rb_sysopen - -z (Errno::ENOENT)
# ARGV = %w[-v    0sandbox /dev/null]
# ARGV = %w[-v -- 0sandbox /dev/null]
# ARGV = %w[-v -- 0sandbox /dev/null foo]      # invalid argument: excess argument(s): ["foo"]
# ARGV = %w[-v -- 0sandbox /dev/null foo bar]  # invalid argument: excess argument(s): ["foo", "bar"]
# ARGV = %w[-v    0sandbox -- /dev/null]
# ARGV = %w[-v -- 0sandbox -- /dev/null]
# ARGV = %w[-v    0sandbox -h]
# ARGV = %w[-v -- 0sandbox -h]

if $PROGRAM_NAME == __FILE__
  # index of "--" or COMMAND
  command_index = ARGV.find_index { |arg| arg == "--" || !arg.start_with?("-") }

  argv_global = command_index.nil? ? ARGV.dup : ARGV[...command_index]
  begin
    argv_global_rest = opt_parser.parse(argv_global)
    assert(argv_global_rest.empty?)

    ARGV.shift(argv_global.length) # discard global options
    ARGV.shift if ARGV[0] == "--"

    raise OptionParser::MissingArgument, "COMMAND not specified" if ARGV.empty?

    command_ = ARGV.shift
    raise OptionParser::InvalidArgument, "no such COMMAND: #{command_}" unless $commands.key?(command_) # rubocop:disable Style/GlobalVars
  rescue OptionParser::ParseError => e
    warn("\e[31m#{e}\e[0m")
    warn("#{__FILE__} --help to see usage")
    exit(1)
  end

  # @type [OptionParser]
  opt_parser = $opt_parsers[command_] # rubocop:disable Style/GlobalVars
  begin
    argv_command_rest = opt_parser.parse!
    exit($commands[command_].call(opts_g)) # rubocop:disable Style/GlobalVars
  rescue OptionParser::ParseError => e
    warn("\e[31m#{e}\e[0m")
    warn("#{__FILE__} #{command_} --help to see usage")
    exit(1)
  rescue MyError => e
    warn(e)
    exit(1)
  end
end

package com.hireos.analytics;

import java.time.Duration;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;

/**
 * Skeleton Flink job for streaming HireOS lifecycle events into metric aggregations.
 * The MVP uses local consumers first; this job is included to show the production path.
 */
public class HireOsMetricsJob {
  public static void main(String[] args) throws Exception {
    StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

    KafkaSource<String> source = KafkaSource.<String>builder()
        .setBootstrapServers("redpanda:9092")
        .setTopics("hireos.answer.scored", "hireos.interview.completed")
        .setGroupId("hireos-flink-metrics")
        .setValueOnlyDeserializer(new SimpleStringSchema())
        .build();

    DataStream<String> stream = env.fromSource(
        source,
        WatermarkStrategy.<String>forBoundedOutOfOrderness(Duration.ofSeconds(5)),
        "hireos-events");

    stream
        .map(value -> "metric_event::" + value)
        .print();

    env.execute("HireOS Metrics Job");
  }
}


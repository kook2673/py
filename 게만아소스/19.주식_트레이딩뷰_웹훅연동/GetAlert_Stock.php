<?php 
    //https://youtu.be/GmR4-AiJjPE 이 영상을 참고하세요!
    //https://blog.naver.com/zacra/223050088124
    header("Content-Type: application/json; charset=utf-8");


    #실제 운영할 때..
    $data =file_get_contents('php://input');

    #임의로 데이터를 만들어서 테스트할 때! 
    #$data = '{"account":"VIRTUAL","area":"US","stock_code":"SPY","type":"limit","side":"sell","price":370.0,"amt":1}';

    $command = "python3 /var/autobot/GetWebhook_Stock.py ". escapeshellarg($data);
    exec($command, $output, $return_var);
    $json_array = json_encode($output);
    echo $json_array

?>
